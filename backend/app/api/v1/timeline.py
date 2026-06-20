"""Timeline endpoints — nested under issues.

GET    /issues/{id}/timeline                    — list timeline events
POST   /issues/{id}/timeline                    — add a comment
PATCH  /issues/{id}/timeline/{event_id}         — edit a comment
DELETE /issues/{id}/timeline/{event_id}         — delete a comment
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.issue import UserSummary
from app.schemas.timeline import (
    TimelineEventCreate,
    TimelineEventResponse,
    TimelineEventUpdate,
    TimelineListResponse,
)
from app.services.timeline_service import timeline_service

router = APIRouter()


def _enrich_event(event: IssueTimeline) -> TimelineEventResponse:
    resp = TimelineEventResponse.model_validate(event)
    if event.actor:
        resp.actor_user = UserSummary.model_validate(event.actor)
    return resp


@router.get(
    "/{issue_id}/timeline",
    response_model=TimelineListResponse,
    summary="List timeline events for an issue",
)
async def list_timeline(
    issue_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineListResponse:
    """Return paginated, chronological timeline events for an issue."""
    events, total = await timeline_service.list_timeline(
        db, issue_id, page=page, size=size, include_internal=True
    )

    # Re-fetch with actor relationship loaded for enrichment
    if events:
        result = await db.execute(
            select(IssueTimeline)
            .options(selectinload(IssueTimeline.actor))
            .where(IssueTimeline.issue_id == issue_id)
            .order_by(IssueTimeline.created_at.asc())
            .offset((page - 1) * size)
            .limit(size)
        )
        events = list(result.scalars().all())

    return TimelineListResponse(
        items=[_enrich_event(e) for e in events],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "/{issue_id}/timeline",
    response_model=TimelineEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to an issue",
)
async def create_comment(
    issue_id: int,
    payload: TimelineEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineEventResponse:
    """Append a comment (or internal note) to the issue timeline."""
    from app.db.models.inbox_item import InboxEventType
    from app.db.models.issue import Issue
    from app.services.inbox_service import inbox_service

    event = await timeline_service.create_event(
        db=db,
        issue_id=issue_id,
        actor_id=current_user.id,
        event_type=TimelineEventType.comment,
        body=payload.body,
        meta=None,
        is_internal=payload.is_internal,
        mentioned_user_ids=payload.mentioned_user_ids or [],
    )
    await db.commit()

    result = await db.execute(
        select(IssueTimeline)
        .options(selectinload(IssueTimeline.actor))
        .where(IssueTimeline.id == event.id)
    )
    event = result.scalar_one()

    # Fan-out inbox notifications inline — simple, synchronous, traceable
    issue_result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = issue_result.scalar_one_or_none()

    if issue is not None:
        mentioned_ids = [str(u) for u in (payload.mentioned_user_ids or [])]
        body = payload.body or ""
        extra = {"body": body, "mentioned_user_ids": mentioned_ids}

        body_snippet = (body[:200] + "…") if body and len(body) > 200 else (body or None)
        snippet_meta = {"body_snippet": body_snippet} if body_snippet else None

        await inbox_service.fan_out(
            db=db,
            trigger=InboxEventType.comment,
            issue=issue,
            actor=current_user,
            timeline_event=event,
            extra_meta=extra,
            meta=snippet_meta,
        )

        if mentioned_ids or "@" in body:
            await inbox_service.fan_out(
                db=db,
                trigger=InboxEventType.mention,
                issue=issue,
                actor=current_user,
                timeline_event=event,
                extra_meta=extra,
                meta=snippet_meta,
            )

        await db.commit()

    from app.tasks.search import embed_issue
    embed_issue.apply_async((issue_id,), countdown=10)

    return _enrich_event(event)


@router.patch(
    "/{issue_id}/timeline/{event_id}",
    response_model=TimelineEventResponse,
    summary="Edit a timeline comment",
)
async def edit_comment(
    issue_id: int,
    event_id: int,
    payload: TimelineEventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineEventResponse:
    """Edit the body of a comment. Only the author (or admin) may edit."""
    event = await timeline_service.edit_comment(db, event_id, payload.body, current_user)
    await db.commit()

    result = await db.execute(
        select(IssueTimeline)
        .options(selectinload(IssueTimeline.actor))
        .where(IssueTimeline.id == event_id)
    )
    event = result.scalar_one()

    from app.tasks.search import embed_issue
    embed_issue.apply_async((issue_id,), countdown=10)

    return _enrich_event(event)


@router.delete(
    "/{issue_id}/timeline/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a timeline comment",
)
async def delete_comment(
    issue_id: int,
    event_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a comment from the timeline. Only the author or admin may delete."""
    result = await db.execute(
        select(IssueTimeline).where(
            IssueTimeline.id == event_id,
            IssueTimeline.issue_id == issue_id,
        )
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timeline event not found")

    if event.event_type != TimelineEventType.comment:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only comments can be deleted")

    is_admin = current_user.role == UserRole.admin
    is_author = event.actor_id == current_user.id
    if not (is_author or is_admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author or admin can delete this comment")

    await db.delete(event)
    await db.commit()
