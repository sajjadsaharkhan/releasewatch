"""Celery tasks — async fan-out of inbox items.

Rather than performing database fan-out synchronously inside the HTTP request,
services can enqueue this task immediately after the DB commit.  The task opens
its own DB session and calls ``InboxFanOutService.fan_out``.
"""

import asyncio
import logging
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.inbox.fan_out_inbox",
    max_retries=3,
    default_retry_delay=10,
    queue="default",
)
def fan_out_inbox(
    self,
    trigger: str,
    issue_id: str,
    actor_id: str,
    timeline_event_id: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create per-user ``InboxItem`` rows for a triggered event.

    Parameters
    ----------
    trigger:
        ``InboxEventType`` value string (e.g. ``"assigned"``).
    issue_id:
        UUID string of the issue the event relates to.
    actor_id:
        UUID string of the user who performed the action.
    timeline_event_id:
        Optional UUID string of the linked ``IssueTimeline`` row.
    extra_meta:
        Optional extra data forwarded to the fan-out logic (e.g. comment body
        for mention parsing).

    Returns
    -------
    dict
        ``{items_created: N}``
    """
    try:
        result = asyncio.run(
            _fan_out_async(trigger, issue_id, actor_id, timeline_event_id, extra_meta)
        )
        return result
    except Exception as exc:
        logger.exception("fan_out_inbox failed: %s", exc)
        raise self.retry(exc=exc)


async def _fan_out_async(
    trigger_str: str,
    issue_id: str,
    actor_id: str,
    timeline_event_id: str | None,
    extra_meta: dict[str, Any] | None,
) -> dict[str, Any]:
    """Internal async implementation — opens a fresh DB session."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

    from app.config import settings
    from app.db.models.inbox_item import InboxEventType
    from app.db.models.issue import Issue
    from app.db.models.issue_timeline import IssueTimeline
    from app.db.models.user import User
    from app.services.inbox_service import inbox_service

    trigger = InboxEventType(trigger_str)

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    items_created = 0
    try:
        async with factory() as db:
            issue_result = await db.execute(
                select(Issue).where(Issue.id == int(issue_id))
            )
            issue = issue_result.scalar_one_or_none()

            actor_result = await db.execute(
                select(User).where(User.id == int(actor_id))
            )
            actor = actor_result.scalar_one_or_none()

            timeline_event = None
            if timeline_event_id:
                te_result = await db.execute(
                    select(IssueTimeline).where(
                        IssueTimeline.id == int(timeline_event_id)
                    )
                )
                timeline_event = te_result.scalar_one_or_none()

            if issue and actor:
                items = await inbox_service.fan_out(
                    db=db,
                    trigger=trigger,
                    issue=issue,
                    actor=actor,
                    timeline_event=timeline_event,
                    extra_meta=extra_meta,
                )
                await db.commit()
                items_created = len(items)
    finally:
        await engine.dispose()

    return {"items_created": items_created}
