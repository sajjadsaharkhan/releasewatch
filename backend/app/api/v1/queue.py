"""Personal queue and board endpoints (slice 10, FR-33–FR-41).

GET    /users/{id}/queue                 — pinned + rest, with what the viewer may do
GET    /users/{id}/board?done_from=&done_to= — one group per board status, in queue order
POST   /users/{id}/queue/move            — drag within a group
POST   /users/{id}/queue/pins            — pin
DELETE /users/{id}/queue/pins/{issue_id} — unpin
GET    /users/{id}/queue/history?from=&to=&actor_id=&not_owner=&action=&type=&q=&page=
                                         — reorders, pins, unpins (append-only), with facet counts

``{id}`` is a user id or ``me``. Policy: the owner, a CTO and an Admin
(``view_queue``, ``reorder_queue``, ``pin``). Ordering lives in
``QueueService`` and ``app/queue_order.py``; these routes authorize and shape.
"""

from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import policy
from app.core.auth import get_current_user
from app.core.clock import get_now
from app.db.models.issue import IssueType, issue_key
from app.db.models.user import User
from app.db.session import get_db
from app.policy import Action, Target
from app.queue_order import PIN_LIMIT
from app.schemas.issue import UserSummary
from app.schemas.queue import (
    BoardColumnOut,
    PersonalBoardResponse,
    QueueEntryOut,
    QueueGroups,
    QueueHistoryItem,
    QueueHistoryResponse,
    QueueMoveRequest,
    QueuePinRequest,
    QueueResponse,
)
from app.services.authz import actor_of, authorize
from app.services.queue_service import build_cards, queue_service

router = APIRouter()

#: The Done column's default window (AC-42), as on the Stream board.
DEFAULT_DONE_DAYS = 7


async def _owner(db: AsyncSession, user_ref: str, viewer: User, action: Action) -> User:
    """Resolve ``me`` / an id to a queue owner and check ``action`` on their queue."""
    if user_ref == "me":
        owner = viewer
    else:
        try:
            owner = await db.get(User, int(user_ref))
        except ValueError:
            owner = None
    if owner is None or not queue_service.has_queue(owner):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    authorize(viewer, action, Target(queue_owner_id=owner.id))
    return owner


@router.get("/users/{user_ref}/queue", response_model=QueueResponse, summary="A personal queue")
async def get_queue(
    user_ref: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> QueueResponse:
    owner = await _owner(db, user_ref, current_user, Action.view_queue)
    return await _queue_response(db, owner, current_user, now)


async def _queue_response(
    db: AsyncSession, owner: User, viewer: User, now: datetime,
) -> QueueResponse:
    rows = await queue_service.queue(db, owner)
    entries = {i.id: e for e, i in rows}
    cards = await build_cards(db, [i for _, i in rows], now, entries)
    groups = QueueGroups()
    for (entry, _), card in zip(rows, cards, strict=True):
        out = QueueEntryOut(
            issue=card, pinned=entry.is_pinned, pin_locked=entry.is_pinned and entry.pin_locked,
            pinned_by=UserSummary.model_validate(entry.pinned_by) if entry.pinned_by else None,
        )
        (groups.pinned if entry.is_pinned else groups.rest).append(out)
    target = Target(queue_owner_id=owner.id)
    reorder = policy.decide(actor_of(viewer), Action.reorder_queue, target)
    pin = policy.decide(actor_of(viewer), Action.pin, target)
    return QueueResponse(
        owner=UserSummary.model_validate(owner),
        groups=groups,
        pin_limit=PIN_LIMIT,
        pins_used=len(groups.pinned),
        can_reorder=reorder.ok,
        can_pin=pin.ok,
        disabled_reason=None if reorder.ok and pin.ok else (
            getattr(reorder, "detail", None) or getattr(pin, "detail", None)
        ),
    )


@router.get(
    "/users/{user_ref}/board", response_model=PersonalBoardResponse, summary="A personal board",
)
async def get_board(
    user_ref: str,
    done_days: int = Query(DEFAULT_DONE_DAYS, ge=1, le=3650),
    done_from: datetime | None = Query(None),
    done_to: datetime | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> PersonalBoardResponse:
    """Open columns follow queue order (AC-41). Done shows items completed in
    ``[done_from, done_to]``, or the last ``done_days`` (default 7, AC-42)."""
    owner = await _owner(db, user_ref, current_user, Action.view_queue)
    if done_from is None:
        done_from, done_to = now - timedelta(days=done_days), None
    columns = await queue_service.board(db, owner, done_from=done_from, done_to=done_to)
    return PersonalBoardResponse(
        owner=UserSummary.model_validate(owner),
        columns=[
            BoardColumnOut(status=col, items=await build_cards(db, issues, now, entries))
            for col, issues, entries in columns
        ],
        done_from=done_from,
        done_to=done_to,
    )


@router.post("/users/{user_ref}/queue/move", response_model=QueueResponse, summary="Reorder")
async def move(
    user_ref: str,
    body: QueueMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> QueueResponse:
    owner = await _owner(db, user_ref, current_user, Action.reorder_queue)
    await queue_service.move(
        db, owner, current_user, body.issue_id, before_id=body.before_id, after_id=body.after_id,
    )
    await db.commit()
    return await _queue_response(db, owner, current_user, now)


@router.post("/users/{user_ref}/queue/pins", response_model=QueueResponse, summary="Pin")
async def pin(
    user_ref: str,
    body: QueuePinRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> QueueResponse:
    owner = await _owner(db, user_ref, current_user, Action.pin)
    await queue_service.pin(db, owner, current_user, body.issue_id)
    await db.commit()
    return await _queue_response(db, owner, current_user, now)


@router.delete(
    "/users/{user_ref}/queue/pins/{issue_id}", response_model=QueueResponse, summary="Unpin",
)
async def unpin(
    user_ref: str,
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> QueueResponse:
    owner = await _owner(db, user_ref, current_user, Action.pin)
    await queue_service.unpin(db, owner, current_user, issue_id)
    await db.commit()
    return await _queue_response(db, owner, current_user, now)


@router.get(
    "/users/{user_ref}/queue/history", response_model=QueueHistoryResponse, summary="Queue history",
)
async def history(
    user_ref: str,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    since: datetime | None = Query(None, alias="from"),
    until: datetime | None = Query(None, alias="to"),
    actor_id: int | None = Query(None),
    not_owner: bool = Query(False),
    action: Literal["reorder", "pin", "unpin"] | None = Query(None),
    item_type: IssueType | None = Query(None, alias="type"),
    q: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QueueHistoryResponse:
    owner = await _owner(db, user_ref, current_user, Action.view_queue)
    rows, total, facets = await queue_service.history(
        db, owner, page=page, size=size, since=since, until=until, actor_id=actor_id,
        not_owner=not_owner, action=action,
        item_type=item_type.value if item_type else None, q=q,
    )
    return QueueHistoryResponse(
        items=[
            QueueHistoryItem(
                id=r.id,
                action=getattr(r.action, "value", r.action),
                actor=UserSummary.model_validate(r.actor) if r.actor else None,
                issue_id=r.issue_id,
                issue_key=issue_key(r.issue.type, r.issue.issue_number) if r.issue else None,
                issue_title=r.issue.title if r.issue else None,
                issue_type=getattr(r.issue.type, "value", r.issue.type) if r.issue else None,
                old_index=r.old_index,
                new_index=r.new_index,
                created_at=r.created_at,
            )
            for r in rows
        ],
        total=total, page=page, size=size, facets=facets,
    )
