"""Telegram notification delivery.

``TelegramSender`` is used by Celery tasks (``app.tasks.notifications``).
It builds a fresh ``TelegramClient`` per call so token/proxy changes from DB
are picked up without restarting the worker.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.telegram.client import TelegramClient, TelegramAPIError
from app.telegram.templates import MESSAGE_TEMPLATES

logger = logging.getLogger(__name__)


class TelegramSender:
    """Renders a notification template and delivers it via the Bot API."""

    def _render(self, template_name: str, context: dict[str, Any]) -> str:
        template = MESSAGE_TEMPLATES.get(template_name)
        if template is None:
            raise ValueError(f"Unknown Telegram template: {template_name!r}")
        return template.format_map(context)

    async def send_notification(
        self,
        chat_id: int,
        template_name: str,
        context: dict[str, Any],
        bot_token: str | None = None,
        proxy_url: str | None = None,
    ) -> bool:
        """Render a template and send it to ``chat_id``.

        Returns True on success, False on any delivery error.
        ``bot_token`` takes precedence over the env-configured token so the
        real token stored in DB settings is used by Celery workers.
        """
        if not bot_token:
            from app.config import settings
            bot_token = settings.TELEGRAM_BOT_TOKEN or None

        if not bot_token:
            logger.warning("Telegram bot token not configured — skipping notification.")
            return False

        text = self._render(template_name, context)
        client = TelegramClient(token=bot_token, proxy_url=proxy_url)
        try:
            await client.send_message(chat_id=chat_id, text=text, parse_mode="HTML")
            return True
        except TelegramAPIError as exc:
            logger.error("Telegram send failed for chat %s: %s", chat_id, exc)
            return False
        except Exception as exc:
            logger.error("Unexpected error sending Telegram message to chat %s: %s", chat_id, exc)
            return False
        finally:
            await client.close()

    async def update_last_sent(self, chat_id: int) -> None:
        """Update last_event_sent_at on the TelegramIntegration row for this chat."""
        try:
            from sqlalchemy import update
            from app.db.models.telegram_integration import TelegramIntegration
            from app.db.session import task_session

            async with task_session() as db:
                await db.execute(
                    update(TelegramIntegration)
                    .where(TelegramIntegration.chat_id == chat_id)
                    .values(last_event_sent_at=datetime.now(tz=timezone.utc))
                )
                await db.commit()
        except Exception:
            logger.warning("Failed to update last_event_sent_at for chat %s", chat_id)


# Module-level singleton used by Celery tasks
telegram_sender = TelegramSender()
