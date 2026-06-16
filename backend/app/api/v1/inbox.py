"""Inbox endpoints — per-user notification feed.

GET  /inbox                  — paginated inbox items
GET  /inbox/unread-count     — count of unread items
POST /inbox/read-all         — mark all as read
POST /inbox/{item_id}/read   — mark single item as read
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user
from app.db.models.inbox_item import InboxItem
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.inbox import ActorInfo, InboxItemResponse, InboxListResponse, UnreadCountResponse

router = APIRouter()


def _build_response(item: InboxItem) -> InboxItemResponse:
    actor_info = None
    if item.actor:
        actor_info = ActorInfo(
            id=item.actor.id,
            name=item.actor.name,
            username=item.actor.username,
            avatar_color=item.actor.avatar_color,
            avatar_url=item.actor.avatar_url,
        )

    issue_id = None
    issue_title = None
    if item.issue:
        issue_id = f"issue-{item.issue.issue_number}"
        issue_title = item.issue.title

    return InboxItemResponse(
        id=item.id,
        type=item.event_type,
        read=item.is_read,
        actor=actor_info,
        issue_id=issue_id,
        issue_title=issue_title,
        timeline_id=item.timeline_id,
        meta=item.meta,
        created_at=item.created_at,
    )


@router.get("", response_model=InboxListResponse, summary="Get inbox")
async def get_inbox(
    is_read: bool | None = Query(None, description="Filter by read status"),
    event_type: str | None = Query(None, description="Filter by event type (e.g. mention, comment, assigned)"),
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InboxListResponse:
    """Return the authenticated user's inbox, newest first."""
    base_query = select(InboxItem).where(InboxItem.user_id == current_user.id)
    if is_read is not None:
        base_query = base_query.where(InboxItem.is_read == is_read)
    if event_type is not None:
        base_query = base_query.where(InboxItem.event_type == event_type)

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar_one()

    unread_query = select(func.count(InboxItem.id)).where(
        InboxItem.user_id == current_user.id,
        InboxItem.is_read.is_(False),
    )
    if event_type is not None:
        unread_query = unread_query.where(InboxItem.event_type == event_type)
    unread_count = (await db.execute(unread_query)).scalar_one()

    result = await db.execute(
        base_query.options(
            selectinload(InboxItem.actor),
            selectinload(InboxItem.issue),
        )
        .order_by(InboxItem.created_at.desc(), InboxItem.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = result.scalars().all()

    return InboxListResponse(
        items=[_build_response(i) for i in items],
        total=total,
        page=page,
        size=size,
        unread_count=unread_count,
    )


@router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    summary="Get unread notification count",
)
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UnreadCountResponse:
    """Return only the count of unread inbox items (cheap poll endpoint)."""
    result = await db.execute(
        select(func.count(InboxItem.id)).where(
            InboxItem.user_id == current_user.id,
            InboxItem.is_read.is_(False),
        )
    )
    return UnreadCountResponse(unread_count=result.scalar_one())


@router.post(
    "/read-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark all inbox items as read",
)
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Bulk-mark all unread inbox items as read."""
    now = datetime.now(tz=timezone.utc)
    await db.execute(
        update(InboxItem)
        .where(InboxItem.user_id == current_user.id, InboxItem.is_read.is_(False))
        .values(is_read=True, read_at=now)
    )
    await db.commit()


@router.post(
    "/{item_id}/read",
    response_model=InboxItemResponse,
    summary="Mark a single inbox item as read",
)
async def mark_item_read(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InboxItemResponse:
    """Mark a specific inbox item as read."""
    from fastapi import HTTPException

    result = await db.execute(
        select(InboxItem)
        .options(
            selectinload(InboxItem.actor),
            selectinload(InboxItem.issue),
        )
        .where(
            InboxItem.id == item_id,
            InboxItem.user_id == current_user.id,
        )
    )
    item = result.scalar_one_or_none()
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inbox item not found")

    if not item.is_read:
        item.is_read = True
        item.read_at = datetime.now(tz=timezone.utc)
        db.add(item)
        await db.commit()
        await db.refresh(item)

    return _build_response(item)
