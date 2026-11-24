"""The To review tab (slice 22, FR-72/FR-73, BR-73).

GET /review-queue?project_ids=&type=&status=to_review|in_review
    Every item in To review or In review, in every project, whoever it is
    assigned to. Tech roles only (``view_review_queue``); Support gets 403.
    Read-only: the status moves happen on the item (BR-60 — no bulk path).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.clock import get_now
from app.db.models.issue import REVIEW_STATUSES, IssueStatus, IssueType
from app.db.models.user import User
from app.db.session import get_db
from app.policy import Action
from app.schemas.queue import ReviewQueueCounts, ReviewQueueResponse, ReviewQueueRow
from app.services.authz import authorize
from app.services.queue_service import build_cards
from app.services.review_queue_service import review_queue_service

router = APIRouter()


@router.get("/review-queue", response_model=ReviewQueueResponse, summary="Waiting for review")
async def get_review_queue(
    project_ids: list[int] | None = Query(None),
    item_type: IssueType | None = Query(None, alias="type"),
    review_status: IssueStatus | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReviewQueueResponse:
    authorize(current_user, Action.view_review_queue)
    if review_status is not None and review_status not in REVIEW_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="status must be a review status",
        )
    counts = await review_queue_service.counts(db, current_user, project_ids)
    rows, truncated = await review_queue_service.rows(
        db, current_user, project_ids=project_ids, item_type=item_type,
        review_status=review_status,
    )
    cards = await build_cards(db, [issue for issue, _ in rows], now)
    return ReviewQueueResponse(
        items=[
            ReviewQueueRow(**card.model_dump(), waiting_since=waiting)
            for card, (_, waiting) in zip(cards, rows, strict=True)
        ],
        counts=ReviewQueueCounts(**counts),
        truncated=truncated,
    )
