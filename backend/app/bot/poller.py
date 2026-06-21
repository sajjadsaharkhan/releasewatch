"""Telegram bot long-poll loop.

``start_polling()`` runs as a background asyncio task for the entire lifetime of
the FastAPI process.  It never exits on its own — it blocks on ``getUpdates``
(30-second long-poll) and handles updates inline.

Token / proxy hot-reload
------------------------
Every 10 iterations the loop re-reads the bot token and proxy URL from
``system_settings``.  If either value changed the current ``Bot`` instance is
shut down and a new one is created transparently — no process restart needed.

If no token is configured yet the loop sleeps 10 s between DB polls and starts
polling as soon as a token appears.
"""

import asyncio
import logging

from sqlalchemy import select
from telegram import Bot
from telegram.error import NetworkError, TimedOut
from telegram.request import HTTPXRequest

from app.config import settings
from app.db.models.system_setting import SystemSetting
from app.bot.handlers import dispatch

logger = logging.getLogger(__name__)

# Re-read DB config every N successful poll iterations.
_DB_CHECK_INTERVAL = 10


async def _read_token_from_db() -> str | None:
    """Read the bot token from system_settings (category='telegram', key='config')."""
    try:
        from app.db.session import _session_factory
        async with _session_factory() as db:
            result = await db.execute(
                select(SystemSetting).where(
                    SystemSetting.category == "telegram",
                    SystemSetting.key == "config",
                    SystemSetting.is_active.is_(True),
                )
            )
            setting = result.scalar_one_or_none()
        if setting and setting.value.get("bot_token"):
            return setting.value["bot_token"]
    except Exception:
        logger.warning("Could not read Telegram token from DB")
    return None


async def _read_proxy_from_db() -> str | None:
    """Read the HTTP proxy URL from system_settings, if configured and enabled."""
    try:
        from app.db.session import _session_factory
        async with _session_factory() as db:
            result = await db.execute(
                select(SystemSetting).where(
                    SystemSetting.category == "proxy",
                    SystemSetting.key == "config",
                    SystemSetting.is_active.is_(True),
                )
            )
            setting = result.scalar_one_or_none()
        if setting and setting.value.get("enabled"):
            return setting.value.get("http") or setting.value.get("https") or None
    except Exception:
        logger.warning("Could not read proxy settings from DB")
    return None


async def _make_bot(token: str, proxy_url: str | None) -> Bot:
    """Create and initialize a Bot instance."""
    http_request = HTTPXRequest(proxy=proxy_url) if proxy_url else HTTPXRequest()
    bot = Bot(token=token, request=http_request)
    await bot.initialize()
    return bot


async def _shutdown_bot(bot: Bot) -> None:
    """Shut down a Bot instance, ignoring errors."""
    try:
        await bot.shutdown()
    except Exception:
        pass


_LOCK_KEY = "rw:telegram:poller:lock"
_LOCK_TTL = 45  # seconds — must exceed the 30s long-poll timeout


async def _try_acquire_lock() -> bool:
    """Attempt to acquire the distributed poller lock in Redis.

    Returns True if this process is now the designated poller, False otherwise.
    Uses SET NX EX so only one uvicorn worker polls at a time.
    """
    try:
        from app.core.redis_client import get_redis_raw
        r = await get_redis_raw()
        return bool(await r.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL))
    except Exception:
        logger.warning("Could not check Redis poller lock — proceeding without lock")
        return True


async def _refresh_lock() -> None:
    """Extend the lock TTL so it doesn't expire mid-poll."""
    try:
        from app.core.redis_client import get_redis_raw
        r = await get_redis_raw()
        await r.expire(_LOCK_KEY, _LOCK_TTL)
    except Exception:
        pass


async def _release_lock() -> None:
    """Release the distributed lock on clean shutdown."""
    try:
        from app.core.redis_client import get_redis_raw
        r = await get_redis_raw()
        await r.delete(_LOCK_KEY)
    except Exception:
        pass


async def start_polling() -> None:
    """Entry point for the background bot task.

    Runs indefinitely.  Polls DB every ``_DB_CHECK_INTERVAL`` iterations for
    token / proxy changes and reinitializes the Bot automatically.
    Gracefully exits on ``asyncio.CancelledError``.

    Uses a Redis distributed lock to ensure only one uvicorn worker (in hot-reload
    mode multiple workers spawn) actually polls Telegram at a time.
    """
    current_token: str | None = None
    current_proxy: str | None = None
    bot: Bot | None = None
    offset: int | None = None
    iteration: int = 0
    holds_lock: bool = False

    logger.info("Telegram bot poller started — checking DB for token every %d iterations", _DB_CHECK_INTERVAL)

    while True:
        try:
            # ── Distributed lock: only one worker should poll ────────────────
            if not holds_lock:
                holds_lock = await _try_acquire_lock()
                if not holds_lock:
                    await asyncio.sleep(15)
                    continue

            # ── DB config check ──────────────────────────────────────────────
            if iteration % _DB_CHECK_INTERVAL == 0:
                new_token = await _read_token_from_db() or settings.TELEGRAM_BOT_TOKEN
                new_proxy = await _read_proxy_from_db()

                if new_token != current_token or new_proxy != current_proxy:
                    if bot is not None:
                        await _shutdown_bot(bot)
                        bot = None
                        offset = None  # reset so we don't miss updates after swap

                    current_token = new_token
                    current_proxy = new_proxy

                    if current_token:
                        bot = await _make_bot(current_token, current_proxy)
                        logger.info(
                            "Telegram bot (re)initialized — proxy=%s",
                            current_proxy or "none",
                        )
                    else:
                        logger.debug("No Telegram token configured — waiting…")

            # ── No token yet: sleep and retry ───────────────────────────────
            if bot is None:
                await asyncio.sleep(10)
                iteration += 1
                continue

            # ── Refresh lock before each long-poll ──────────────────────────
            await _refresh_lock()

            # ── Long-poll for updates ────────────────────────────────────────
            updates = await bot.get_updates(
                offset=offset,
                timeout=30,
                allowed_updates=["message"],
            )
            for update in updates:
                if update.message:
                    from app.db.session import _session_factory
                    async with _session_factory() as db:
                        try:
                            await dispatch(update.message, bot, db)
                        except Exception:
                            logger.exception("Error handling update %s", update.update_id)
                offset = update.update_id + 1

            iteration += 1

        except asyncio.CancelledError:
            logger.info("Telegram bot polling stopped")
            if bot:
                await _shutdown_bot(bot)
            if holds_lock:
                await _release_lock()
            break

        except (NetworkError, TimedOut) as exc:
            logger.warning("Telegram network error: %s — retrying in 5s", exc)
            await asyncio.sleep(5)

        except Exception:
            logger.exception("Unexpected error in Telegram poll loop — retrying in 10s")
            await asyncio.sleep(10)
