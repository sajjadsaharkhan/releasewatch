"""Timeline endpoints — nested under issues.

GET   /issues/{id}/timeline                    — list timeline events
POST  /issues/{id}/timeline                    — add a comment
PATCH /issues/{id}/timeline/{event_id}         — edit a comment
"""

import uuid
from typing import List

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.timeline import (
    TimelineEventCreate,
    TimelineEventResponse,
    TimelineEventUpdate,
    TimelineListResponse,
)
from app.services.timeline_service import timeline_service
from app.db.models.issue_timeline import TimelineEventType

router = APIRouter()


@router.get(
    "/{issue_id}/timeline",
    response_model=TimelineListResponse,
    summary="List timeline events for an issue",
)
async def list_timeline(
    issue_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineListResponse:
    """Return paginated, chronological timeline events for an issue.

    Internal events are visible to all authenticated team members.
    """
    events, total = await timeline_service.list_timeline(
        db, issue_id, page=page, size=size, include_internal=True
    )
    return TimelineListResponse(
        items=[TimelineEventResponse.model_validate(e) for e in events],
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
    issue_id: uuid.UUID,
    payload: TimelineEventCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineEventResponse:
    """Append a comment (or internal note) to the issue timeline.

    Mention parsing (``@username``) and inbox fan-out are handled asynchronously
    via the ``fan_out_inbox`` Celery task.
    """
    event = await timeline_service.create_event(
        db=db,
        issue_id=issue_id,
        actor_id=current_user.id,
        event_type=TimelineEventType.comment,
        body=payload.body,
        meta=None,
        is_internal=payload.is_internal,
    )
    await db.commit()
    await db.refresh(event)

    # Enqueue mention detection + inbox fan-out
    from app.tasks.inbox import fan_out_inbox
    from app.db.models.inbox_item import InboxEventType

    fan_out_inbox.apply_async(
        kwargs={
            "trigger": InboxEventType.comment.value,
            "issue_id": str(issue_id),
            "actor_id": str(current_user.id),
            "timeline_event_id": str(event.id),
            "extra_meta": {"body": payload.body},
        }
    )

    return TimelineEventResponse.model_validate(event)


@router.patch(
    "/{issue_id}/timeline/{event_id}",
    response_model=TimelineEventResponse,
    summary="Edit a timeline comment",
)
async def edit_comment(
    issue_id: uuid.UUID,
    event_id: uuid.UUID,
    payload: TimelineEventUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimelineEventResponse:
    """Edit the body of a comment. Only the author (or admin) may edit."""
    event = await timeline_service.edit_comment(db, event_id, payload.body, current_user)
    await db.commit()
    await db.refresh(event)
    return TimelineEventResponse.model_validate(event)
