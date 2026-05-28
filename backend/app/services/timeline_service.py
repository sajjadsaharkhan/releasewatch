"""TimelineService — append-only event log for issues.

All events (system-generated or user-authored) are written through this service
so that the audit trail is consistent and pagination is predictable.
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.user import User


class TimelineService:
    """Manages reading and writing ``IssueTimeline`` events."""

    # ── Creation ──────────────────────────────────────────────────────────────

    async def create_event(
        self,
        db: AsyncSession,
        issue_id: int,
        actor_id: int | None,
        event_type: TimelineEventType,
        body: str | None,
        meta: dict[str, Any] | None,
        is_internal: bool = False,
        mentioned_user_ids: list[int] | None = None,
    ) -> IssueTimeline:
        """Append a timeline event to an issue's log.

        Parameters
        ----------
        db:
            Active async session (event is flushed, not committed).
        issue_id:
            UUID of the parent issue.
        actor_id:
            UUID of the user performing the action; ``None`` for system events.
        event_type:
            The ``TimelineEventType`` enum value.
        body:
            Free-text body (comment text, MR URL, etc.).
        meta:
            Structured diff payload (e.g. ``{from: 'new', to: 'triaged'}``).
        is_internal:
            If ``True``, the event is hidden from non-team-member viewers.

        Returns
        -------
        IssueTimeline
            The newly created, flushed event row.
        """
        if mentioned_user_ids:
            meta = {**(meta or {}), "mentioned_user_ids": [str(u) for u in mentioned_user_ids]}

        event = IssueTimeline(
            issue_id=issue_id,
            actor_id=actor_id,
            event_type=event_type,
            body=body,
            meta=meta,
            is_internal=is_internal,
        )
        db.add(event)
        await db.flush()
        return event

    # ── Listing ───────────────────────────────────────────────────────────────

    async def list_timeline(
        self,
        db: AsyncSession,
        issue_id: int,
        page: int = 1,
        size: int = 50,
        include_internal: bool = True,
    ) -> tuple[list[IssueTimeline], int]:
        """Return a paginated, chronological list of timeline events.

        Parameters
        ----------
        db:
            Active async session.
        issue_id:
            UUID of the issue whose timeline to fetch.
        page:
            1-based page number.
        size:
            Page size (max events per page).
        include_internal:
            If ``False``, internal events are filtered out (for non-team viewers).

        Returns
        -------
        tuple[list[IssueTimeline], int]
            ``(events, total_count)`` — total_count is the count before pagination.
        """
        base_query = select(IssueTimeline).where(IssueTimeline.issue_id == issue_id)
        if not include_internal:
            base_query = base_query.where(IssueTimeline.is_internal.is_(False))

        count_result = await db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar_one()

        events_result = await db.execute(
            base_query.order_by(IssueTimeline.created_at.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
        events = list(events_result.scalars().all())
        return events, total

    # ── Edit comment ──────────────────────────────────────────────────────────

    async def edit_comment(
        self,
        db: AsyncSession,
        event_id: int,
        body: str,
        current_user: User,
    ) -> IssueTimeline:
        """Edit the body of a ``comment`` timeline event.

        Only the original author (or an admin) may edit a comment.

        Parameters
        ----------
        db:
            Active async session.
        event_id:
            UUID of the ``IssueTimeline`` row to edit.
        body:
            New comment body text.
        current_user:
            The authenticated user making the edit.

        Returns
        -------
        IssueTimeline
            The updated event row.

        Raises
        ------
        HTTPException(404)
            If the event is not found.
        HTTPException(403)
            If the user is not allowed to edit this event.
        HTTPException(400)
            If the event type is not ``comment``.
        """
        result = await db.execute(
            select(IssueTimeline).where(IssueTimeline.id == event_id)
        )
        event = result.scalar_one_or_none()
        if event is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline event not found")

        if event.event_type != TimelineEventType.comment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only comment events can be edited.",
            )

        from app.db.models.user import UserRole

        is_admin = current_user.role == UserRole.admin
        is_author = event.actor_id == current_user.id
        if not (is_author or is_admin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the comment author or an admin can edit this comment.",
            )

        event.body = body
        event.meta = {
            **(event.meta or {}),
            "edited_by": str(current_user.id),
            "edited_at": datetime.now(tz=timezone.utc).isoformat(),
        }
        db.add(event)
        await db.flush()
        return event


# Module-level singleton
timeline_service = TimelineService()
