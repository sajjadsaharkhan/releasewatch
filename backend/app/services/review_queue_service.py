"""ReviewQueueService — everything waiting for QA, in every project (slice 22, FR-73).

Read-only. The queue is the set of items in ``REVIEW_STATUSES`` that the caller
can see, in non-archived projects; nobody is assigned as reviewer (BR-73).
``waiting_since`` is read from the timeline (the latest move into the item's
current status), never stored.
"""

from datetime import datetime

from sqlalchemy import case, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue import (
    PRIORITY_ORDER, REVIEW_STATUSES, Issue, IssueStatus, IssueType,
)
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.project import Project
from app.db.models.user import User
from app.services.authz import visibility_clause
from app.services.queue_service import card_load_options

#: Above this many rows the list is cut and ``truncated`` is true.
REVIEW_QUEUE_LIMIT = 500

_REVIEW_VALUES = tuple(s.value for s in REVIEW_STATUSES)


def _base(viewer: User, project_ids: list[int] | None):
    q = (
        select(Issue)
        .join(Project, Project.id == Issue.project_id)
        .where(
            Issue.deleted_at.is_(None),
            Project.archived_at.is_(None),
            Issue.status.in_(_REVIEW_VALUES),
            visibility_clause(viewer),
        )
    )
    if project_ids:
        q = q.where(Issue.project_id.in_(project_ids))
    return q


class ReviewQueueService:
    async def counts(
        self, db: AsyncSession, viewer: User, project_ids: list[int] | None,
    ) -> dict[str, int]:
        sub = _base(viewer, project_ids).subquery()
        rows = (await db.execute(
            select(sub.c.status, func.count()).group_by(sub.c.status)
        )).all()
        by_status = {str(getattr(s, "value", s)): n for s, n in rows}
        to_review = by_status.get(IssueStatus.to_review.value, 0)
        in_review = by_status.get(IssueStatus.in_review.value, 0)
        return {"to_review": to_review, "in_review": in_review, "total": to_review + in_review}

    async def rows(
        self,
        db: AsyncSession,
        viewer: User,
        *,
        project_ids: list[int] | None,
        item_type: IssueType | None,
        review_status: IssueStatus | None,
    ) -> tuple[list[tuple[Issue, datetime]], bool]:
        """``[(issue, waiting_since)]`` in display order, and whether it was cut."""
        # The latest move into each item's current status, in one grouped query.
        to_status = literal_column("issue_timeline.meta ->> 'to'").label("to_status")
        moved = (
            select(
                IssueTimeline.issue_id.label("issue_id"),
                to_status,
                func.max(IssueTimeline.created_at).label("at"),
            )
            .where(IssueTimeline.event_type == TimelineEventType.status_changed.value)
            .group_by(IssueTimeline.issue_id, to_status)
            .subquery()
        )
        waiting = func.coalesce(moved.c.at, Issue.updated_at)
        q = (
            _base(viewer, project_ids)
            .add_columns(waiting.label("waiting_since"))
            .outerjoin(
                moved, (moved.c.issue_id == Issue.id) & (moved.c.to_status == Issue.status),
            )
            .options(*card_load_options())
        )
        if item_type is not None:
            q = q.where(Issue.type == item_type.value)
        if review_status is not None:
            q = q.where(Issue.status == review_status.value)
        # To review sorts before In review: REVIEW_STATUSES is declared in that order.
        status_rank = case(*((Issue.status == v, n) for n, v in enumerate(_REVIEW_VALUES)))
        q = q.order_by(
            func.lower(Project.name), Project.id, status_rank, PRIORITY_ORDER, waiting, Issue.id,
        ).limit(REVIEW_QUEUE_LIMIT + 1)
        found = (await db.execute(q)).all()
        truncated = len(found) > REVIEW_QUEUE_LIMIT
        return [(i, w) for i, w in found[:REVIEW_QUEUE_LIMIT]], truncated


review_queue_service = ReviewQueueService()
