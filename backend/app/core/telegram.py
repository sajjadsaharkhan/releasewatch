"""Telegram bot integration — notification delivery.

The bot itself (command handling, long polling) lives in ``app.bot``.
This module owns message templates and the delivery service used by Celery tasks.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError

from app.config import settings

logger = logging.getLogger(__name__)

# ── Message templates ─────────────────────────────────────────────────────────
MESSAGE_TEMPLATES: dict[str, str] = {
    "issue_filed": (
        "🐛 *New issue filed* — #{issue_number}\n"
        "*{title}*\n"
        "Severity: `{severity}` | Release: `{version}`\n"
        "[View issue]({issue_url})"
    ),
    "assigned": (
        "👤 *Issue assigned to you* — #{issue_number}\n"
        "*{title}*\n"
        "Severity: `{severity}` | Release: `{version}`\n"
        "[View issue]({issue_url})"
    ),
    "fixed": (
        "✅ *Fix ready for verification* — #{issue_number}\n"
        "*{title}*\n"
        "Fixed by: {developer}\n"
        "[View issue]({issue_url})"
    ),
    "fix_verified": (
        "🎉 *Fix verified* — #{issue_number}\n"
        "*{title}*\n"
        "Verified by: {verifier} | Outcome: `{outcome}`\n"
        "[View issue]({issue_url})"
    ),
    "regression": (
        "🔁 *Regression detected* — #{issue_number}\n"
        "*{title}*\n"
        "Release: `{version}` | Occurrence #{regression_number}\n"
        "[View issue]({issue_url})"
    ),
    "release_approved": (
        "🚀 *Release approved* — `{version}`\n"
        "Project: {project_name}\n"
        "Approved by: {approver}\n"
        "Note: {note}"
    ),
    "release_blocked": (
        "🚫 *Release blocked* — `{version}`\n"
        "Project: {project_name}\n"
        "Blocked by: {blocker}\n"
        "Reason: {note}"
    ),
    "mention": (
        "💬 *You were mentioned* — #{issue_number}\n"
        "*{title}*\n"
        "By: {actor}\n"
        "_{excerpt}_\n"
        "[View timeline]({timeline_url})"
    ),
}


class TelegramService:
    """Wrapper around the async Telegram Bot API for notification delivery."""

    def __init__(self) -> None:
        token = settings.TELEGRAM_BOT_TOKEN
        self._bot: Bot | None = Bot(token=token) if token else None

    def _render(self, template_name: str, context: dict[str, Any]) -> str:
        template = MESSAGE_TEMPLATES.get(template_name)
        if template is None:
            raise ValueError(f"Unknown Telegram template: {template_name!r}")
        return template.format_map(context)

    async def _send_message(self, chat_id: int, text: str) -> bool:
        if self._bot is None:
            logger.warning("Telegram bot token not configured — skipping notification.")
            return False
        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
            return True
        except TelegramError as exc:
            logger.error("Telegram send failed for chat %s: %s", chat_id, exc)
            return False

    async def send_notification(
        self,
        chat_id: int,
        template_name: str,
        context: dict[str, Any],
    ) -> bool:
        """Send a notification from a named template to the given Telegram chat."""
        text = self._render(template_name, context)
        return await self._send_message(chat_id, text)

    async def update_last_sent(self, chat_id: int) -> None:
        """Update last_event_sent_at on the TelegramIntegration row for this chat."""
        try:
            from sqlalchemy import select, update
            from app.db.models.telegram_integration import TelegramIntegration
            from app.db.session import _session_factory

            async with _session_factory() as db:
                await db.execute(
                    update(TelegramIntegration)
                    .where(TelegramIntegration.chat_id == chat_id)
                    .values(last_event_sent_at=datetime.now(tz=timezone.utc))
                )
                await db.commit()
        except Exception:
            logger.warning("Failed to update last_event_sent_at for chat %s", chat_id)


# Module-level singleton
telegram_service = TelegramService()
