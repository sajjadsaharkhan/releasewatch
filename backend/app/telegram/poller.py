"""Telegram bot long-poll loop.

Designed to run as a standalone process (via ``run_bot.py``) decoupled from
the FastAPI server.  Uses a Redis distributed lock so multiple bot-service
replicas don't duplicate polls.

Token / proxy hot-reload
------------------------
Every ``_DB_CHECK_INTERVAL`` iterations the loop re-reads the token and proxy
from ``system_settings``.  If either value changed the current client is
closed and a new one is created transparently — no restart needed.

If no token is configured the loop sleeps 10 s between DB polls and starts
as soon as a token appears.

Self-healing
------------
A long-lived httpx client can wedge after a proxy or network blip — every
request then times out waiting for a pooled connection, forever, while a fresh
client works at once (2026-10-12: the poller failed for ~44 h until a restart).
After ``_MAX_NETWORK_ERRORS`` consecutive network errors the client is closed
and rebuilt. The offset is kept: same bot, so updates resume where they stopped.
"""

import asyncio
import logging

import httpx

from app.telegram.client import TelegramClient, TelegramAPIError
from app.telegram.config import load_bot_token, load_proxy_url
from app.telegram.handlers import dispatch

logger = logging.getLogger(__name__)

_DB_CHECK_INTERVAL = 10
_LOCK_KEY = "rw:telegram:poller:lock"
_LOCK_TTL = 45  # seconds — must exceed the 30 s long-poll timeout
_MAX_NETWORK_ERRORS = 3  # consecutive failures before the client is rebuilt


# ── Distributed lock helpers ───────────────────────────────────────────────────

async def _try_acquire_lock() -> bool:
    try:
        from app.core.redis_client import get_redis_raw
        r = await get_redis_raw()
        return bool(await r.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL))
    except Exception:
        logger.warning("Could not check Redis poller lock — proceeding without lock")
        return True


async def _refresh_lock() -> None:
    try:
        from app.core.redis_client import get_redis_raw
        r = await get_redis_raw()
        await r.expire(_LOCK_KEY, _LOCK_TTL)
    except Exception:
        pass


async def _release_lock() -> None:
    try:
        from app.core.redis_client import get_redis_raw
        r = await get_redis_raw()
        await r.delete(_LOCK_KEY)
    except Exception:
        pass


# ── Main poll loop ─────────────────────────────────────────────────────────────

async def start_polling() -> None:
    """Entry point for the standalone bot process.

    Runs indefinitely.  Polls DB every ``_DB_CHECK_INTERVAL`` iterations for
    token / proxy changes and reinitialises the client transparently.
    Exits cleanly on ``asyncio.CancelledError`` or ``KeyboardInterrupt``.
    """
    current_token: str | None = None
    current_proxy: str | None = None
    client: TelegramClient | None = None
    offset: int | None = None
    iteration: int = 0
    holds_lock: bool = False
    network_errors: int = 0

    logger.info(
        "Telegram bot poller started — checking DB for token every %d iterations",
        _DB_CHECK_INTERVAL,
    )

    while True:
        try:
            # ── Distributed lock: only one replica should poll ───────────────
            if not holds_lock:
                holds_lock = await _try_acquire_lock()
                if not holds_lock:
                    await asyncio.sleep(15)
                    continue

            # ── DB config hot-reload ─────────────────────────────────────────
            if iteration % _DB_CHECK_INTERVAL == 0:
                new_token = await load_bot_token()
                new_proxy = await load_proxy_url()

                if new_token != current_token or new_proxy != current_proxy:
                    if client is not None:
                        await client.close()
                        client = None
                        offset = None  # reset so we don't miss updates after swap

                    current_token = new_token
                    current_proxy = new_proxy

                    if current_token:
                        client = TelegramClient(token=current_token, proxy_url=current_proxy)
                        logger.info(
                            "Telegram client (re)initialised — proxy=%s",
                            current_proxy or "none",
                        )
                    else:
                        logger.debug("No Telegram token configured — waiting…")

            # ── No token yet: sleep and retry ────────────────────────────────
            if client is None:
                await asyncio.sleep(10)
                iteration += 1
                continue

            # ── Refresh lock before each long-poll ──────────────────────────
            await _refresh_lock()

            # ── Long-poll for updates ────────────────────────────────────────
            updates = await client.get_updates(offset=offset, timeout=30)
            if network_errors:
                logger.info("Telegram polling recovered after %d network errors", network_errors)
                network_errors = 0
            for update in updates:
                msg = update.get("message")
                if msg:
                    from app.db.session import _session_factory
                    async with _session_factory() as db:
                        try:
                            await dispatch(msg, client, db)
                        except Exception:
                            logger.exception("Error handling update %s", update.get("update_id"))
                offset = update["update_id"] + 1

            iteration += 1

        except asyncio.CancelledError:
            logger.info("Telegram bot polling stopped")
            if client:
                await client.close()
            if holds_lock:
                await _release_lock()
            break

        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            # httpx timeouts often have an empty message — the type is what tells
            # a pool timeout from a proxy that refuses the connection.
            network_errors += 1
            logger.warning(
                "Telegram network error %d: %s %s — retrying in 5s",
                network_errors, type(exc).__name__, exc,
            )
            if network_errors % _MAX_NETWORK_ERRORS == 0 and client is not None:
                try:
                    await client.close()
                except Exception:
                    logger.warning("Could not close the wedged Telegram client", exc_info=True)
                client = TelegramClient(token=current_token, proxy_url=current_proxy)
                logger.warning(
                    "Telegram client rebuilt after %d consecutive network errors — proxy=%s",
                    network_errors, current_proxy or "none",
                )
            await asyncio.sleep(5)

        except TelegramAPIError as exc:
            logger.warning("Telegram API error: %s — retrying in 5s", exc)
            await asyncio.sleep(5)

        except Exception:
            logger.exception("Unexpected error in Telegram poll loop — retrying in 10s")
            await asyncio.sleep(10)
