"""Celery tasks — the hourly due-date notices to assignees (slice 10, PRD §13)."""

import asyncio
import logging
from datetime import UTC, datetime

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def notify_due_items(now: datetime) -> dict[str, list[int]]:
    """Tell each assignee once when an item is due within 24 hours and once when
    it's overdue. Takes ``now`` (slice 01's clock rule) so tests control it."""
    from app.db.session import task_session
    from app.services.queue_service import queue_service

    async with task_session() as db:
        notified = await queue_service.notify_due_items(db, now)
        await db.commit()
    return notified


@celery_app.task(name="app.tasks.queue.notify_due_items", queue="default")
def notify_due_items_task() -> dict:
    notified = asyncio.run(notify_due_items(datetime.now(tz=UTC)))
    logger.info("Due-date notices sent: %s", notified)
    return notified
