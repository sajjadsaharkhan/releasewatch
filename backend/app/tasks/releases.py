"""Celery tasks — the daily overdue-release check (slice 09, PRD §13)."""

import asyncio
import logging
from datetime import UTC, datetime

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def run_overdue_check(now: datetime) -> list[int]:
    """Tell active CTOs about releases that passed their target ship date — once
    per date. Takes ``now`` (slice 01's clock rule) so tests control it."""
    from app.db.session import task_session
    from app.services.release_service import release_service

    async with task_session() as db:
        notified = await release_service.notify_overdue(db, now)
        await db.commit()
    return notified


@celery_app.task(name="app.tasks.releases.notify_overdue_releases", queue="default")
def notify_overdue_releases() -> dict:
    notified = asyncio.run(run_overdue_check(datetime.now(tz=UTC)))
    logger.info("Overdue releases notified: %s", notified)
    return {"notified": notified}
