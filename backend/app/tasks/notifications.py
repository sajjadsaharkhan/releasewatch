"""Celery tasks — Telegram notification delivery with durable outbox.

Delivery state is tracked on ``inbox_items.telegram_status`` so notifications
survive bot restarts, Telegram outages, and Redis blips:

  pending → immediate Celery task attempts delivery → sent / failed
  failed  → ``flush_telegram_notifications`` beat task retries with backoff
  skipped → not applicable (no template, matrix says no, no TG account)

No notification is ever silently dropped: if the bot can't reach Telegram, the
item stays ``failed`` and is retried indefinitely until it goes through.

Note on DB access
-----------------
Celery prefork tasks run inside ``asyncio.run()`` which creates a fresh event
loop per call.  SQLAlchemy's connection pool binds connections to the event
loop that created them, making pooled connections unusable across tasks.
All DB access here goes through ``task_session()`` (NullPool) to avoid this.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from celery import Task

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _backoff(retry_count: int) -> int:
    """Exponential backoff in seconds, capped at 30 minutes."""
    return min(30 * (2 ** retry_count), 1800)


class _AsyncTask(Task):
    def run_async(self, coro):
        return asyncio.run(coro)


async def _update_inbox_item(inbox_item_id: int, success: bool, error: str | None = None) -> None:
    """Update telegram_status on an inbox item after a send attempt."""
    try:
        from sqlalchemy import select
        from app.db.session import task_session
        from app.db.models.inbox_item import InboxItem
        from app.db.models.telegram_integration import TelegramIntegration

        async with task_session() as db:
            result = await db.execute(
                select(InboxItem).where(InboxItem.id == inbox_item_id)
            )
            item = result.scalar_one_or_none()
            if not item:
                return

            if item.telegram_status == "sent":
                return  # already delivered (dedup — acks_late re-run)

            now = datetime.now(timezone.utc)
            if success:
                item.telegram_status = "sent"
                item.telegram_error = None
                tg_result = await db.execute(
                    select(TelegramIntegration).where(
                        TelegramIntegration.user_id == item.user_id
                    )
                )
                tg = tg_result.scalar_one_or_none()
                if tg:
                    tg.last_event_sent_at = now
            else:
                retry_count = (item.telegram_retry_count or 0) + 1
                item.telegram_retry_count = retry_count
                item.telegram_status = "failed"
                item.telegram_error = (error or "send_notification returned False")[:512]
                item.telegram_next_retry_at = now + timedelta(seconds=_backoff(retry_count))

            await db.commit()
    except Exception:
        logger.warning(
            "Could not update inbox item %s telegram_status", inbox_item_id, exc_info=True
        )


@celery_app.task(
    bind=True,
    base=_AsyncTask,
    name="app.tasks.notifications.send_telegram_notification",
    queue="notifications",
)
def send_telegram_notification(
    self: Task,
    chat_id: int,
    template_name: str,
    context: dict[str, Any],
    bot_token: str | None = None,
    proxy_url: str | None = None,
    inbox_item_id: int | None = None,
) -> bool:
    """Send a Telegram notification and update the inbox item outbox status.

    If ``inbox_item_id`` is provided the result is written back to
    ``inbox_items.telegram_status``.  The ``flush_telegram_notifications`` beat
    task retries any rows that remain ``failed`` or ``pending``.
    """
    from app.telegram.sender import telegram_sender

    async def _send():
        success = await telegram_sender.send_notification(
            chat_id=chat_id,
            template_name=template_name,
            context=context,
            bot_token=bot_token,
            proxy_url=proxy_url,
        )
        if inbox_item_id:
            await _update_inbox_item(inbox_item_id, success)
        return success

    try:
        result = self.run_async(_send())
        if result:
            logger.info(
                "Telegram notification '%s' delivered to chat %s", template_name, chat_id
            )
        else:
            logger.warning(
                "Telegram '%s' failed for chat %s — beat task will retry",
                template_name,
                chat_id,
            )
        return result
    except Exception as exc:
        logger.warning("Telegram task error for chat %s: %s", chat_id, exc)
        if inbox_item_id:
            self.run_async(_update_inbox_item(inbox_item_id, False, str(exc)))
        return False


@celery_app.task(
    base=_AsyncTask,
    name="app.tasks.notifications.flush_telegram_notifications",
    queue="notifications",
)
def flush_telegram_notifications() -> dict[str, int]:
    """Retry all pending/failed Telegram inbox items whose backoff has elapsed.

    Called by Celery beat every 60 seconds and once on bot startup so no
    notification is stuck indefinitely.
    """
    async def _flush():
        from sqlalchemy import select, or_
        from app.db.models.inbox_item import InboxItem
        from app.db.models.telegram_integration import TelegramIntegration
        from app.db.models.system_setting import SystemSetting
        from app.db.session import task_session
        from app.telegram.sender import telegram_sender
        from app.config import settings as app_settings

        now = datetime.now(timezone.utc)
        sent = failed = skipped = 0

        async with task_session() as db:
            # Load bot token and proxy from DB directly (same session, no nesting).
            tg_cfg_row = (await db.execute(
                select(SystemSetting).where(
                    SystemSetting.category == "telegram",
                    SystemSetting.key == "config",
                    SystemSetting.is_active.is_(True),
                )
            )).scalar_one_or_none()
            bot_token: str | None = (
                (tg_cfg_row.value or {}).get("bot_token") if tg_cfg_row else None
            ) or app_settings.TELEGRAM_BOT_TOKEN or None

            if not bot_token:
                logger.warning("flush_telegram_notifications: no bot token, skipping")
                return {"sent": 0, "failed": 0, "skipped": 0, "no_token": True}

            proxy_cfg_row = (await db.execute(
                select(SystemSetting).where(
                    SystemSetting.category == "proxy",
                    SystemSetting.key == "config",
                    SystemSetting.is_active.is_(True),
                )
            )).scalar_one_or_none()
            proxy_url: str | None = None
            if proxy_cfg_row and (proxy_cfg_row.value or {}).get("enabled"):
                proxy_url = (
                    proxy_cfg_row.value.get("socks5")
                    or proxy_cfg_row.value.get("http")
                    or proxy_cfg_row.value.get("https")
                )

            result = await db.execute(
                select(InboxItem)
                .where(InboxItem.telegram_status.in_(["pending", "failed"]))
                .where(
                    or_(
                        InboxItem.telegram_next_retry_at.is_(None),
                        InboxItem.telegram_next_retry_at <= now,
                    )
                )
                .limit(100)
            )
            items = list(result.scalars().all())

            if not items:
                return {"sent": 0, "failed": 0, "skipped": 0}

            user_ids = [item.user_id for item in items]
            tg_by_user = {
                t.user_id: t
                for t in (
                    await db.execute(
                        select(TelegramIntegration)
                        .where(TelegramIntegration.user_id.in_(user_ids))
                        .where(TelegramIntegration.is_active.is_(True))
                    )
                ).scalars().all()
            }

            for item in items:
                tg = tg_by_user.get(item.user_id)
                if not tg:
                    item.telegram_status = "skipped"
                    skipped += 1
                    continue

                tg_ctx = (item.meta or {}).get("tg_context")
                if not tg_ctx:
                    item.telegram_status = "skipped"
                    item.telegram_error = "no tg_context in meta"
                    skipped += 1
                    continue

                success = await telegram_sender.send_notification(
                    chat_id=tg.chat_id,
                    template_name=item.event_type,
                    context=tg_ctx,
                    bot_token=bot_token,
                    proxy_url=proxy_url,
                )

                now_ts = datetime.now(timezone.utc)
                if success:
                    item.telegram_status = "sent"
                    item.telegram_error = None
                    tg.last_event_sent_at = now_ts
                    sent += 1
                else:
                    retry_count = (item.telegram_retry_count or 0) + 1
                    item.telegram_retry_count = retry_count
                    item.telegram_status = "failed"
                    item.telegram_error = "send_notification returned False"
                    item.telegram_next_retry_at = now_ts + timedelta(
                        seconds=_backoff(retry_count)
                    )
                    failed += 1

            await db.commit()

        if sent or failed:
            logger.info(
                "Telegram flush complete: sent=%d failed=%d skipped=%d", sent, failed, skipped
            )
        return {"sent": sent, "failed": failed, "skipped": skipped}

    return asyncio.run(_flush())


@celery_app.task(
    name="app.tasks.notifications.bulk_notify_team",
    queue="notifications",
)
def bulk_notify_team(
    chat_ids: list[int],
    template_name: str,
    context: dict[str, Any],
    bot_token: str | None = None,
    proxy_url: str | None = None,
) -> dict[str, Any]:
    """Enqueue individual Telegram notifications for a list of chat IDs."""
    for cid in chat_ids:
        send_telegram_notification.apply_async(
            args=[cid, template_name, context],
            kwargs={"bot_token": bot_token, "proxy_url": proxy_url},
            queue="notifications",
        )
    return {"enqueued": len(chat_ids)}
