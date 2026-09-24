"""Subscribers (slice 06) — who hears an item's Support-audience events.

The one place that writes ``issue_subscribers``. Inserts are
``ON CONFLICT DO NOTHING`` so the first reason wins and two concurrent merges
subscribing the same reporter never collide.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue_subscriber import IssueSubscriber, SubscriptionReason


async def subscribe(
    db: AsyncSession, issue_id: int, user_id: int | None, reason: SubscriptionReason,
) -> None:
    if user_id is None:
        return
    await db.execute(
        insert(IssueSubscriber)
        .values(issue_id=issue_id, user_id=user_id, reason=reason.value)
        .on_conflict_do_nothing(index_elements=["issue_id", "user_id"])
    )


async def subscriber_ids(db: AsyncSession, issue_id: int) -> set[int]:
    result = await db.execute(
        select(IssueSubscriber.user_id).where(IssueSubscriber.issue_id == issue_id)
    )
    return set(result.scalars().all())
