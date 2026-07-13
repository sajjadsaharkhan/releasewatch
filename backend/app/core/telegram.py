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
from telegram.request import HTTPXRequest

from app.config import settings

logger = logging.getLogger(__name__)

# ── Message templates (Telegram HTML parse mode) ──────────────────────────────
# Keys align with InboxEventType values so inbox_service can dispatch by event key.
# Dynamic fields injected by _dispatch_telegram (all text values are HTML-escaped):
#   issue_number, title, issue_url, comment_url, actor, actor_url, severity, excerpt
#   project_name, release_name, release_deadline
#   old_status/new_status, old_environment/new_environment, old_release/new_release
MESSAGE_TEMPLATES: dict[str, str] = {
    "filed": (
        "🐛 <b>New issue filed!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Severity: <code>{severity}</code>"
    ),
    "assigned": (
        "👋 <b>You've been assigned!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Severity: <code>{severity}</code>\n"
        "\n"
        "<i>Time to shine ⭐ — assigned by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    "comment": (
        "💬 <b>New comment on your issue</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a>:</i> \"{excerpt}\"\n"
        "\n"
        "<a href=\"{comment_url}\">Jump to comment →</a>"
    ),
    "mention": (
        "📣 <b>Psst — you were mentioned!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> said:</i> \"{excerpt}\"\n"
        "\n"
        "<a href=\"{comment_url}\">View mention →</a>"
    ),
    "status_changed": (
        "⚡️ <b>Status just moved!</b>\n"
        "🐛 <a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "🗂 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "📤 From: <code>{old_status}</code>\n"
        "📥 To:      <code>{new_status}</code>\n"
        "\n"
        "🧑‍💻 Moved by <a href=\"{actor_url}\">{actor}</a>"
    ),
    "regression": (
        "🔁 <b>Regression detected!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Severity: <code>{severity}</code>\n"
        "\n"
        "<i>This one came back from the dead 👻</i>"
    ),
    "fixed": (
        "🛠 <b>Fix ready for verification!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> says it's done — QA, your turn! 🔍</i>"
    ),
    "verified": (
        "🎉 <b>Fix verified!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> gave it the green light ✅</i>"
    ),
    "blocker_filed": (
        "🚨 <b>RELEASE BLOCKER FILED!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "Severity: <code>{severity}</code>\n"
        "⏰ <b>Deadline:</b> {release_deadline}\n"
        "\n"
        "<i>Filed by <a href=\"{actor_url}\">{actor}</a> — all hands on deck! 🚒</i>"
    ),
    "blocker_cleared": (
        "✅ <b>Blocker cleared!</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> cleared the path — release is unblocked 🚀</i>"
    ),
    "environment_changed": (
        "🌍 <b>Environment changed</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "📤 From: <code>{old_environment}</code>\n"
        "📥 To:      <code>{new_environment}</code>\n"
        "\n"
        "<i>Updated by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    "release_changed": (
        "📦 <b>Issue moved to a different release</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📁 <b>{project_name}</b>\n"
        "\n"
        "📤 From: <code>{old_release}</code>\n"
        "📥 To:      <code>{new_release}</code>\n"
        "\n"
        "<i>Moved by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    "attachment_added": (
        "📎 <b>New attachment added</b>\n"
        "<a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "📦 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "<i><a href=\"{actor_url}\">{actor}</a> attached a file</i>"
    ),
    "severity_changed": (
        "🔥 <b>Severity just changed!</b>\n"
        "🐛 <a href=\"{issue_url}\">#{issue_number} — {title}</a>\n"
        "🗂 <b>{project_name}</b> · <code>{release_name}</code>\n"
        "\n"
        "📤 From: <code>{old_severity}</code>\n"
        "📥 To:      <code>{new_severity}</code>\n"
        "\n"
        "⚠️ Updated by <a href=\"{actor_url}\">{actor}</a>"
    ),
    "release_gate": (
        "🚀 <b>Release gate update</b> — <code>{version}</code>\n"
        "📦 <b>{project_name}</b>\n"
        "Gate: <code>{gate_status}</code>\n"
        "\n"
        "<i>Updated by <a href=\"{actor_url}\">{actor}</a></i>"
    ),
    "release_approved": (
        "🥳 <b>Release approved!</b> — <code>{version}</code>\n"
        "📦 <b>{project_name}</b>\n"
        "\n"
        "<i>Approved by {approver}</i> 🎉\n"
        "{note}"
    ),
    "release_blocked": (
        "🚫 <b>Release blocked!</b> — <code>{version}</code>\n"
        "📦 <b>{project_name}</b>\n"
        "\n"
        "<i>Blocked by {blocker}</i>\n"
        "Reason: {note}"
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

    async def _send_message(
        self, chat_id: int, text: str, bot_token: str | None = None, proxy_url: str | None = None
    ) -> bool:
        # An explicit token (e.g. the real token persisted in DB settings) takes
        # precedence over the env-configured singleton bot, which may hold only a
        # placeholder value.
        if bot_token:
            try:
                request = HTTPXRequest(proxy=proxy_url) if proxy_url else HTTPXRequest()
                async with Bot(token=bot_token, request=request) as bot:
                    await bot.send_message(
                        chat_id=chat_id, text=text, parse_mode=ParseMode.HTML
                    )
                return True
            except TelegramError as exc:
                logger.error("Telegram send failed for chat %s: %s", chat_id, exc)
                return False

        if self._bot is None:
            logger.warning("Telegram bot token not configured — skipping notification.")
            return False
        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.HTML,
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
        bot_token: str | None = None,
        proxy_url: str | None = None,
    ) -> bool:
        """Send a notification from a named template to the given Telegram chat."""
        text = self._render(template_name, context)
        return await self._send_message(chat_id, text, bot_token=bot_token, proxy_url=proxy_url)

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
