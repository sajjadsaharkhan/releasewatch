"""Subscribers (slice 06) — who hears an item's Support-audience events.

The one place that writes ``issue_subscribers``. Inserts are
``ON CONFLICT DO NOTHING`` so the first reason wins and two concurrent merges
subscribing the same reporter never collide.
"""

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue_subscriber import IssueSubscriber, SubscriptionReason
from app.db.models.issue_timeline import TimelineEventType
from app.db.models.user import User


async def subscribe(
    db: AsyncSession, issue_id: int, user_id: int | None, reason: SubscriptionReason,
) -> bool:
    """Add the subscription; ``True`` when a row was actually inserted."""
    if user_id is None:
        return False
    result = await db.execute(
        insert(IssueSubscriber)
        .values(issue_id=issue_id, user_id=user_id, reason=reason.value)
        .on_conflict_do_nothing(index_elements=["issue_id", "user_id"])
        .returning(IssueSubscriber.id)
    )
    return result.first() is not None


async def unsubscribe(db: AsyncSession, issue_id: int, user_id: int) -> bool:
    """Drop the subscription; ``True`` when a row was actually deleted."""
    result = await db.execute(
        delete(IssueSubscriber)
        .where(IssueSubscriber.issue_id == issue_id, IssueSubscriber.user_id == user_id)
        .returning(IssueSubscriber.id)
    )
    return result.first() is not None


async def set_subscription(
    db: AsyncSession, issue_id: int, user_id: int, *, subscribed: bool,
) -> bool:
    """The Subscribe button: change the caller's subscription and, only when it
    really changed, record it on the timeline for every member to see. Returns
    whether anything changed, so a double click writes one entry, not two."""
    from app.services.timeline_service import timeline_service

    if subscribed:
        changed = await subscribe(db, issue_id, user_id, SubscriptionReason.manual)
    else:
        changed = await unsubscribe(db, issue_id, user_id)
    if changed:
        await timeline_service.create_event(
            db, issue_id, user_id,
            TimelineEventType.subscribed if subscribed else TimelineEventType.unsubscribed,
            None, None,
        )
    return changed


async def subscription_state(
    db: AsyncSession, issue_ids: list[int], user_id: int,
) -> dict[int, tuple[int, bool]]:
    """``{issue_id: (subscriber_count, is_subscribed)}`` for the given items."""
    if not issue_ids:
        return {}
    rows = await db.execute(
        select(
            IssueSubscriber.issue_id,
            func.count(),
            func.coalesce(func.bool_or(IssueSubscriber.user_id == user_id), False),
        )
        .where(IssueSubscriber.issue_id.in_(issue_ids))
        .group_by(IssueSubscriber.issue_id)
    )
    return {i: (count, bool(mine)) for i, count, mine in rows.all()}


async def subscriber_ids(db: AsyncSession, issue_id: int) -> set[int]:
    result = await db.execute(
        select(IssueSubscriber.user_id).where(IssueSubscriber.issue_id == issue_id)
    )
    return set(result.scalars().all())


async def subscribers(db: AsyncSession, issue_id: int) -> list[tuple[User, IssueSubscriber]]:
    """Who is subscribed, oldest first."""
    rows = await db.execute(
        select(User, IssueSubscriber)
        .join(IssueSubscriber, IssueSubscriber.user_id == User.id)
        .where(IssueSubscriber.issue_id == issue_id)
        .order_by(IssueSubscriber.created_at, IssueSubscriber.id)
    )
    return [(u, sub) for u, sub in rows.all()]
