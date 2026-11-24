"""Celery task — send the Support channel outbox (slice 21, FR-71).

Every 15 s by beat: rows that are due, oldest first. A failure keeps the row
``pending`` with the same backoff as ``flush_telegram_notifications`` and gives
up after eight attempts (``failed``). The action that created the event never
waits for any of this.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from app.tasks.celery_app import celery_app
from app.tasks.notifications import _backoff

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 8
BATCH_SIZE = 50


async def send_due_posts(now: datetime) -> dict[str, int]:
    """Send every due post. Takes ``now`` (slice 01's clock rule); never raises."""
    from sqlalchemy import select

    from app.db.models.project import Project
    from app.db.models.support_channel_post import SupportChannelPost
    from app.db.session import task_session
    from app.telegram.channel_posts import render
    from app.telegram.client import TelegramClient
    from app.telegram.config import load_runtime

    sent = failed = dropped = 0
    try:
        async with task_session() as db:
            rows = (await db.execute(
                select(SupportChannelPost)
                .where(SupportChannelPost.status == "pending", SupportChannelPost.not_before <= now)
                .order_by(SupportChannelPost.id)
                .limit(BATCH_SIZE)
                .with_for_update(skip_locked=True)
            )).scalars().all()
            if not rows:
                return {"sent": 0, "failed": 0, "dropped": 0}
            token, proxy_url = await load_runtime(db)
            if not token:
                logger.warning("send_due_posts: no bot token, leaving %d posts pending", len(rows))
                return {"sent": 0, "failed": 0, "dropped": 0, "no_token": 1}

            client = TelegramClient(token=token, proxy_url=proxy_url)
            try:
                for row in rows:
                    project = await db.get(Project, row.project_id)
                    unwanted = (
                        project is None or not project.support_channel_enabled
                        or project.support_chat_id is None
                        # moved there and back inside the window: nothing to say
                        or (row.kind == "status" and row.first_status == row.last_status)
                    )
                    if unwanted:
                        await db.delete(row)
                        dropped += 1
                        continue
                    try:
                        await client.send_message(
                            chat_id=project.support_chat_id,
                            text=render(row.kind, row.first_status, row.last_status, row.payload),
                            message_thread_id=project.support_thread_id,
                        )
                    except Exception as exc:
                        row.attempts += 1
                        row.last_error = str(exc).removeprefix("sendMessage failed: ")[:512]
                        if row.attempts >= MAX_ATTEMPTS:
                            row.status = "failed"
                            logger.error(
                                "Support channel post %s gave up after %d attempts: %s",
                                row.id, row.attempts, row.last_error,
                            )
                        else:
                            row.not_before = now + timedelta(seconds=_backoff(row.attempts))
                        failed += 1
                    else:
                        row.status = "sent"
                        row.sent_at = now
                        row.last_error = None
                        sent += 1
            finally:
                await client.close()
            await db.commit()
    except Exception:
        logger.warning("send_due_posts failed", exc_info=True)
    return {"sent": sent, "failed": failed, "dropped": dropped}


@celery_app.task(name="app.tasks.support_channel.send_support_channel_posts", queue="notifications")
def send_support_channel_posts() -> dict[str, int]:
    return asyncio.run(send_due_posts(datetime.now(tz=UTC)))
