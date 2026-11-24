"""Return requests — Support's "Problem is back" and its decision (slice 20, FR-68/69).

POST /issues/{id}/return-requests         — press Problem is back (or add to the pending request)
GET  /issues/{id}/return-requests         — the item's requests, newest first
GET  /projects/{ref}/return-requests      — a project's triage queue of Pending requests
POST /return-requests/{id}/confirm        — reject the item (the ordinary Reject from Done)
POST /return-requests/{id}/dismiss        — keep it Done, with a public comment

Routes are thin: Policy decides who may act, ``ReturnRequestService`` writes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.v1.projects import _get_project_or_404
from app.core.auth import get_current_user
from app.db.models.issue import Issue
from app.db.models.user import User
from app.db.session import get_db
from app.policy import Action
from app.schemas.return_request import (
    ReturnRequestCreate, ReturnRequestDismiss, ReturnRequestQueue, ReturnRequestResponse,
)
from app.services.authz import (
    authorize, authorize_issue, issue_target, load_visible_issue, project_target,
)
from app.services.return_request_service import return_request_service

router = APIRouter()


@router.post(
    "/issues/{issue_id}/return-requests",
    response_model=ReturnRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Problem is back",
)
async def create_return_request(
    issue_id: int,
    payload: ReturnRequestCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReturnRequestResponse:
    """A Support user says a Done item's problem is back (FR-68). The comment is
    required; with a Pending request the press is added to it. 409 ``not_done``
    unless the item is Done, 403 for tech roles."""
    issue = await authorize_issue(db, issue_id, current_user, Action.request_return)
    request = await return_request_service.request(db, issue, current_user, payload)
    response = await return_request_service.to_response(db, request)
    await db.commit()
    return response


@router.get(
    "/issues/{issue_id}/return-requests",
    response_model=list[ReturnRequestResponse],
    summary="An item's return requests",
)
async def list_return_requests(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReturnRequestResponse]:
    await load_visible_issue(db, issue_id, current_user)
    return await return_request_service.list_for_issue(db, issue_id)


@router.get(
    "/projects/{ref}/return-requests",
    response_model=ReturnRequestQueue,
    summary="A project's Pending return requests",
)
async def project_return_requests(
    ref: str,
    status_: str = Query("pending", alias="status", pattern="^pending$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReturnRequestQueue:
    """The triage queue's Return requests tab (FR-69), oldest first — policy ``triage``."""
    project = await _get_project_or_404(db, ref)
    authorize(current_user, Action.triage, project_target(project))
    return await return_request_service.queue(db, project.id)


@router.get(
    "/return-requests",
    response_model=ReturnRequestQueue,
    summary="Pending return requests across projects",
)
async def all_return_requests(
    status_: str = Query("pending", alias="status", pattern="^pending$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReturnRequestQueue:
    """The triage page's Return requests tab with no project selected, and the
    sidebar counter — policy ``triage`` (any tech role)."""
    authorize(current_user, Action.triage)
    return await return_request_service.queue(db)


async def _decide_target(db: AsyncSession, request_id: int, user: User) -> None:
    request = await return_request_service.get(db, request_id)
    if request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Return request not found")
    issue = (await db.execute(
        select(Issue).where(Issue.id == request.issue_id).options(selectinload(Issue.project))
    )).scalar_one()
    # 404 for an item the caller can't see; 403 for Support, which can see but not decide.
    await load_visible_issue(db, issue.id, user)
    authorize(user, Action.decide_return_request, issue_target(issue, issue.project))


@router.post(
    "/return-requests/{request_id}/confirm",
    response_model=ReturnRequestResponse,
    summary="Confirm a return request",
)
async def confirm_return_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReturnRequestResponse:
    """Reject the item exactly as Reject from Done does, with the request's first
    comment as the reason (FR-69). 409 ``request_closed`` when already decided."""
    await _decide_target(db, request_id, current_user)
    request = await return_request_service.confirm(db, request_id, current_user)
    response = await return_request_service.to_response(db, request)
    await db.commit()
    return response


@router.post(
    "/return-requests/{request_id}/dismiss",
    response_model=ReturnRequestResponse,
    summary="Dismiss a return request",
)
async def dismiss_return_request(
    request_id: int,
    payload: ReturnRequestDismiss,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReturnRequestResponse:
    """Close the request and leave the item Done; a public comment is required (422
    ``reason_required``)."""
    await _decide_target(db, request_id, current_user)
    request = await return_request_service.dismiss(db, request_id, current_user, payload.comment)
    response = await return_request_service.to_response(db, request)
    await db.commit()
    return response
