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
