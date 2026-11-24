"""DB-backed Telegram configuration loader.

Reads the bot token and optional proxy URL from ``system_settings`` so changes
take effect without restarting any process.
"""

import logging

from sqlalchemy import select

logger = logging.getLogger(__name__)


async def load_bot_token() -> str | None:
    """Return the bot token from DB, falling back to env config."""
    try:
        from app.db.session import _session_factory
        from app.db.models.system_setting import SystemSetting

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

    from app.config import settings
    return settings.TELEGRAM_BOT_TOKEN or None


async def load_proxy_url() -> str | None:
    """Return the HTTP/SOCKS proxy URL from DB if proxy is enabled."""
    try:
        from app.db.session import _session_factory
        from app.db.models.system_setting import SystemSetting

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
            return (
                setting.value.get("socks5")
                or setting.value.get("http")
                or setting.value.get("https")
                or None
            )
    except Exception:
        logger.warning("Could not read proxy settings from DB")
    return None


async def load_runtime(db) -> tuple[str | None, str | None]:
    """``(bot_token, proxy_url)`` read through ``db`` — for code that already holds
    a session (the Support channel sender and its test message). Same precedence
    as ``flush_telegram_notifications``: the DB setting first, then the env token."""
    from app.config import settings
    from app.db.models.system_setting import SystemSetting

    async def _setting(category: str) -> dict:
        row = (await db.execute(
            select(SystemSetting).where(
                SystemSetting.category == category,
                SystemSetting.key == "config",
                SystemSetting.is_active.is_(True),
            )
        )).scalar_one_or_none()
        return (row.value or {}) if row else {}

    token = (await _setting("telegram")).get("bot_token") or settings.TELEGRAM_BOT_TOKEN or None
    proxy = await _setting("proxy")
    proxy_url = None
    if proxy.get("enabled"):
        proxy_url = proxy.get("socks5") or proxy.get("http") or proxy.get("https") or None
    return token, proxy_url
