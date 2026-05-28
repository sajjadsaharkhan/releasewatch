"""Telegram bot integration — notifications and link-account flow.

The bot uses ``python-telegram-bot`` in async mode.  The ``TelegramService``
class is instantiated once at module level and reused across requests.

Message templates use Python f-string style placeholders filled from a
``context`` dict passed by callers.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
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
    """Wrapper around the async Telegram Bot API.

    All methods are ``async`` and safe to call from FastAPI route handlers or
    Celery tasks (via ``asyncio.run`` in the task).
    """

    def __init__(self) -> None:
        token = settings.TELEGRAM_BOT_TOKEN
        self._bot: Bot | None = Bot(token=token) if token else None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a message template with context values."""
        template = MESSAGE_TEMPLATES.get(template_name)
        if template is None:
            raise ValueError(f"Unknown Telegram template: {template_name!r}")
        return template.format_map(context)

    async def _send_message(self, telegram_user_id: int, text: str) -> bool:
        """Send a Markdown message to a Telegram user.

        Returns
        -------
        bool
            ``True`` on success, ``False`` if the bot is not configured or
            the user has blocked it.
        """
        if self._bot is None:
            logger.warning("Telegram bot token not configured — skipping notification.")
            return False
        try:
            await self._bot.send_message(
                chat_id=telegram_user_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
            return True
        except TelegramError as exc:
            logger.error("Telegram send failed for user %s: %s", telegram_user_id, exc)
            return False

    # ── Public API ────────────────────────────────────────────────────────────

    async def send_notification(
        self,
        telegram_user_id: int,
        template_name: str,
        context: dict[str, Any],
    ) -> bool:
        """Send a notification from a named template.

        Parameters
        ----------
        telegram_user_id:
            The recipient's Telegram user ID (not their @handle).
        template_name:
            Key in ``MESSAGE_TEMPLATES``.
        context:
            Values used to fill in the template placeholders.

        Returns
        -------
        bool
            ``True`` if the message was delivered successfully.
        """
        text = self._render(template_name, context)
        return await self._send_message(telegram_user_id, text)

    async def handle_connect_command(
        self,
        telegram_user_id: int,
        telegram_handle: str,
        token: str,
        db: AsyncSession,
    ) -> str:
        """Link a Telegram account to a Releasewatch user via a one-time token.

        Invoked when the bot receives ``/connect <token>`` from a Telegram user.

        Parameters
        ----------
        telegram_user_id:
            Sender's Telegram user ID.
        telegram_handle:
            Sender's Telegram username (without @).
        token:
            The one-time connect token retrieved from ``GET /auth/telegram/token``.
        db:
            Async database session.

        Returns
        -------
        str
            A human-readable reply to send back to the Telegram user.
        """
        from app.db.models.user import User  # avoid circular imports

        now = datetime.now(tz=timezone.utc)
        result = await db.execute(
            select(User).where(
                User.connect_token == token,
                User.connect_token_expires > now,
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            return "❌ Invalid or expired token. Generate a new one from your Releasewatch settings."

        user.telegram_user_id = telegram_user_id
        user.telegram_handle = telegram_handle
        user.telegram_connected_at = now
        user.connect_token = None
        user.connect_token_expires = None
        await db.commit()

        return (
            f"✅ Your Telegram account has been linked to Releasewatch!\n"
            f"You'll receive notifications for issues assigned to {user.name}."
        )

    async def handle_status_command(
        self,
        telegram_user_id: int,
        issue_id: str,
        db: AsyncSession,
    ) -> str:
        """Reply with the current status of an issue.

        Invoked when the bot receives ``/status <issue_id>`` from a Telegram user.

        Parameters
        ----------
        telegram_user_id:
            Sender's Telegram user ID (used for access control — only team members).
        issue_id:
            UUID or issue number string supplied by the user.
        db:
            Async database session.

        Returns
        -------
        str
            A human-readable reply describing the issue state.
        """
        from app.db.models.issue import Issue
        from app.db.models.user import User

        # Verify the sender is a linked Releasewatch user
        result = await db.execute(
            select(User).where(User.telegram_user_id == telegram_user_id)
        )
        requesting_user = result.scalar_one_or_none()
        if requesting_user is None:
            return "❌ Your Telegram account is not linked. Use /connect <token> to link it."

        # Look up by issue_number (numeric string) or by integer id
        issue = None
        if issue_id.isdigit():
            res = await db.execute(
                select(Issue).where(Issue.issue_number == int(issue_id))
            )
            issue = res.scalar_one_or_none()
            if issue is None:
                res = await db.execute(select(Issue).where(Issue.id == int(issue_id)))
                issue = res.scalar_one_or_none()

        if issue is None:
            return f"❌ Issue `{issue_id}` not found."

        return (
            f"📋 Issue #{issue.issue_number}: *{issue.title}*\n"
            f"Status: `{issue.status}` | Severity: `{issue.severity}`\n"
            f"Regression: {'Yes' if issue.is_regression else 'No'}"
        )


# Module-level singleton
telegram_service = TelegramService()
