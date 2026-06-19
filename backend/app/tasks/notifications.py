"""Celery tasks — Telegram notification delivery with retry logic.

Tasks are enqueued by services after DB commits so the push is decoupled from
the HTTP request lifecycle.
"""

import asyncio
import logging
from typing import Any

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


class _AsyncTask(Task):
    """Base task class that runs an async function in a new event loop.

    Celery workers run synchronously, so we use ``asyncio.run`` to bridge
    the gap.  This keeps service code clean and fully async.
    """

    def run_async(self, coro):
        return asyncio.run(coro)


@celery_app.task(
    bind=True,
    base=_AsyncTask,
    name="app.tasks.notifications.send_telegram_notification",
    max_retries=3,
    default_retry_delay=30,
    queue="notifications",
)
def send_telegram_notification(
    self: Task,
    chat_id: int,
    template_name: str,
    context: dict[str, Any],
) -> bool:
    """Send a Telegram notification to a user via the bot.

    Retries up to 3 times with exponential back-off on transient failures.

    Parameters
    ----------
    chat_id:
        Recipient's Telegram chat ID (from ``telegram_integrations.chat_id``).
    template_name:
        Key in ``MESSAGE_TEMPLATES`` (e.g. ``"assigned"``).
    context:
        Template fill-in values.

    Returns
    -------
    bool
        ``True`` if the message was delivered successfully.
    """
    from app.core.telegram import telegram_service

    async def _send():
        success = await telegram_service.send_notification(
            chat_id=chat_id,
            template_name=template_name,
            context=context,
        )
        if success:
            await telegram_service.update_last_sent(chat_id)
        return success

    try:
        result = self.run_async(_send())
        if not result:
            raise RuntimeError("Telegram send returned False (possibly blocked by user).")
        logger.info("Telegram notification '%s' delivered to chat %s", template_name, chat_id)
        return True
    except Exception as exc:
        logger.warning(
            "Telegram notification failed (attempt %d/%d): %s",
            self.request.retries + 1,
            self.max_retries + 1,
            exc,
        )
        try:
            # Exponential back-off: 30s, 90s, 270s
            countdown = 30 * (3 ** self.request.retries)
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            logger.error(
                "Exhausted retries for Telegram notification to chat %s (template=%s)",
                chat_id,
                template_name,
            )
            return False


@celery_app.task(
    name="app.tasks.notifications.bulk_notify_team",
    queue="notifications",
)
def bulk_notify_team(
    chat_ids: list[int],
    template_name: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    """Enqueue individual Telegram notifications for a list of chat IDs.

    Parameters
    ----------
    chat_ids:
        List of ``telegram_integrations.chat_id`` values to notify.
    template_name:
        Notification template key.
    context:
        Template context shared across all recipients.
    """
    for cid in chat_ids:
        send_telegram_notification.apply_async(
            args=[cid, template_name, context],
            queue="notifications",
        )
    return {"enqueued": len(chat_ids)}
