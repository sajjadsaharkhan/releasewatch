"""Issue endpoints.

GET    /issues                     — list issues (with filters)
POST   /issues                     — file a new issue
GET    /issues/{id}                — get issue detail
PATCH  /issues/{id}                — update issue fields
DELETE /issues/{id}                — delete issue (admin only)
POST   /issues/{id}/triage         — triage an issue
POST   /issues/{id}/fix            — mark as fixed
POST   /issues/{id}/verify         — verify the fix
POST   /issues/{id}/reopen         — reopen a closed/verified issue
POST   /issues/{id}/duplicate      — link as duplicate
"""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_role
from app.db.models.issue import Issue, IssueSeverity, IssueStatus
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.issue import (
    DuplicateRequest,
    FixRequest,
    IssueCreate,
    IssueListResponse,
    IssueResponse,
    IssueUpdate,
    TriageRequest,
    VerifyRequest,
)
from app.services.issue_service import issue_service

router = APIRouter()


@router.get("", response_model=IssueListResponse, summary="List issues")
async def list_issues(
    project_id: Optional[uuid.UUID] = Query(None),
    release_id: Optional[uuid.UUID] = Query(None),
    status: Optional[IssueStatus] = Query(None),
    severity: Optional[IssueSeverity] = Query(None),
    assignee_id: Optional[uuid.UUID] = Query(None),
    is_regression: Optional[bool] = Query(None),
    is_release_blocker: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueListResponse:
    """Return a paginated, filterable list of issues."""
    from sqlalchemy import func

    query = select(Issue)
    if project_id:
        query = query.where(Issue.project_id == project_id)
    if release_id:
        query = query.where(Issue.release_id == release_id)
    if status:
        query = query.where(Issue.status == status)
    if severity:
        query = query.where(Issue.severity == severity)
    if assignee_id:
        query = query.where(Issue.assignee_id == assignee_id)
    if is_regression is not None:
        query = query.where(Issue.is_regression == is_regression)
    if is_release_blocker is not None:
        query = query.where(Issue.is_release_blocker == is_release_blocker)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    result = await db.execute(
        query.order_by(Issue.created_at.desc()).offset((page - 1) * size).limit(size)
    )
    issues = result.scalars().all()

    return IssueListResponse(
        items=[IssueResponse.model_validate(i) for i in issues],
        total=total,
        page=page,
        size=size,
    )


@router.post(
    "",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="File a new issue",
)
async def create_issue(
    payload: IssueCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """File a new issue against a release. Any authenticated user can file issues."""
    issue = await issue_service.create(db, payload, current_user)
    await db.commit()
    await db.refresh(issue)
    return IssueResponse.model_validate(issue)


@router.get("/{issue_id}", response_model=IssueResponse, summary="Get issue detail")
async def get_issue(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Return a single issue by UUID."""
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    return IssueResponse.model_validate(issue)


@router.patch("/{issue_id}", response_model=IssueResponse, summary="Update issue fields")
async def update_issue(
    issue_id: uuid.UUID,
    payload: IssueUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Partially update editable fields of an issue (title, description, labels, etc.)."""
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(issue, field, value)
    db.add(issue)
    await db.commit()
    await db.refresh(issue)
    return IssueResponse.model_validate(issue)


@router.delete(
    "/{issue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete issue (admin only)",
)
async def delete_issue(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> None:
    """Hard-delete an issue (admin only). Use with caution."""
    result = await db.execute(select(Issue).where(Issue.id == issue_id))
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    await db.delete(issue)
    await db.commit()


@router.post("/{issue_id}/triage", response_model=IssueResponse, summary="Triage an issue")
async def triage_issue(
    issue_id: uuid.UUID,
    payload: TriageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        require_role(UserRole.triage_lead, UserRole.cto, UserRole.admin)
    ),
) -> IssueResponse:
    """Triage: assign the issue and confirm severity (triage lead / CTO / admin)."""
    issue = await issue_service.triage(
        db, issue_id, payload.assignee_id, payload.severity, current_user
    )
    await db.commit()
    await db.refresh(issue)
    return IssueResponse.model_validate(issue)


@router.post("/{issue_id}/fix", response_model=IssueResponse, summary="Mark issue as fixed")
async def mark_fixed(
    issue_id: uuid.UUID,
    payload: FixRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Developer marks the issue as fixed (optionally linking the MR)."""
    issue = await issue_service.mark_fixed(db, issue_id, payload.mr_url, current_user)
    await db.commit()
    await db.refresh(issue)
    return IssueResponse.model_validate(issue)


@router.post("/{issue_id}/verify", response_model=IssueResponse, summary="Verify a fix")
async def verify_fix(
    issue_id: uuid.UUID,
    payload: VerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """QA verifies the developer's fix. Outcome: pass | fail | partial."""
    issue = await issue_service.verify_fix(db, issue_id, payload.outcome, current_user)
    await db.commit()
    await db.refresh(issue)
    return IssueResponse.model_validate(issue)


@router.post("/{issue_id}/reopen", response_model=IssueResponse, summary="Reopen issue")
async def reopen_issue(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Reopen a verified or closed issue, returning it to in_progress."""
    issue = await issue_service.reopen(db, issue_id, current_user)
    await db.commit()
    await db.refresh(issue)
    return IssueResponse.model_validate(issue)


@router.post(
    "/{issue_id}/duplicate",
    response_model=IssueResponse,
    summary="Link issue as duplicate",
)
async def link_duplicate(
    issue_id: uuid.UUID,
    payload: DuplicateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Mark this issue as a duplicate of another issue and close it."""
    issue = await issue_service.link_duplicate(db, issue_id, payload.parent_id, current_user)
    await db.commit()
    await db.refresh(issue)
    return IssueResponse.model_validate(issue)
