"""Issue endpoints.

GET    /issues                     — list issues (filters + sort handled server-side)
GET    /issues/export              — export issues as CSV
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

import csv
import io
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, require_role
from app.db.models.issue import Issue, IssueSeverity, IssueStatus
from app.db.models.label import Label
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.issue import (
    DuplicateRequest,
    FixRequest,
    IssueCreate,
    IssueListResponse,
    IssueResponse,
    IssueUpdate,
    LabelDetail,
    TriageRequest,
    UserSummary,
    VerifyRequest,
)
from app.services.issue_service import issue_service

router = APIRouter()

_SEVERITY_ORDER = case(
    (Issue.severity == IssueSeverity.blocker, 0),
    (Issue.severity == IssueSeverity.critical, 1),
    (Issue.severity == IssueSeverity.major, 2),
    (Issue.severity == IssueSeverity.minor, 3),
    (Issue.severity == IssueSeverity.enhancement, 4),
    else_=5,
)


def _apply_filters(
    query,
    *,
    project_id,
    release_id,
    status,
    severity,
    assignee_id,
    is_regression,
    is_release_blocker,
    unassigned,
    labels,
    search,
):
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
    if unassigned:
        query = query.where(Issue.assignee_id.is_(None))
    if labels:
        query = query.where(or_(*[Issue.labels.any(name) for name in labels]))
    if search:
        from sqlalchemy import String as SAString, cast
        query = query.where(
            or_(
                Issue.title.ilike(f"%{search}%"),
                cast(Issue.issue_number, SAString).ilike(f"%{search}%"),
            )
        )
    return query


def _apply_sort(query, sort: str):
    if sort == "oldest":
        return query.order_by(Issue.created_at.asc(), Issue.issue_number.asc())
    elif sort == "severity":
        return query.order_by(_SEVERITY_ORDER, Issue.created_at.desc(), Issue.issue_number.desc())
    elif sort == "updated":
        return query.order_by(Issue.updated_at.desc(), Issue.issue_number.desc())
    else:
        return query.order_by(Issue.created_at.desc(), Issue.issue_number.desc())


async def _build_enriched_responses(
    issues: list[Issue], db: AsyncSession
) -> list[IssueResponse]:
    """Build IssueResponse objects with embedded user/label/release data."""
    all_label_names = {name for issue in issues for name in (issue.labels or [])}
    label_map: dict[str, Label] = {}
    if all_label_names:
        result = await db.execute(select(Label).where(Label.name.in_(all_label_names)))
        for label in result.scalars().all():
            label_map[label.name] = label

    responses = []
    for issue in issues:
        resp = IssueResponse.model_validate(issue)
        enriched = resp.model_copy(update={
            "assignee_user": (
                UserSummary.model_validate(issue.assignee) if issue.assignee else None
            ),
            "reporter_user": (
                UserSummary.model_validate(issue.reporter) if issue.reporter else None
            ),
            "labels_detail": [
                LabelDetail(id=label_map[n].id, name=n, color=label_map[n].color)
                for n in (issue.labels or [])
                if n in label_map
            ],
            "release_version": issue.release.version if issue.release else None,
        })
        responses.append(enriched)
    return responses


@router.get("", response_model=IssueListResponse, summary="List issues")
async def list_issues(
    project_id: Optional[uuid.UUID] = Query(None),
    release_id: Optional[uuid.UUID] = Query(None),
    status: Optional[IssueStatus] = Query(None),
    severity: Optional[IssueSeverity] = Query(None),
    assignee_id: Optional[uuid.UUID] = Query(None),
    is_regression: Optional[bool] = Query(None),
    is_release_blocker: Optional[bool] = Query(None),
    unassigned: Optional[bool] = Query(None),
    labels: Optional[List[str]] = Query(None),
    sort: str = Query("newest"),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueListResponse:
    """Return a paginated, filterable, sortable list of issues."""
    filter_kwargs = dict(
        project_id=project_id,
        release_id=release_id,
        status=status,
        severity=severity,
        assignee_id=assignee_id,
        is_regression=is_regression,
        is_release_blocker=is_release_blocker,
        unassigned=unassigned,
        labels=labels,
        search=search,
    )

    count_q = _apply_filters(select(func.count(Issue.id)), **filter_kwargs)
    total = (await db.execute(count_q)).scalar_one()

    fetch_q = select(Issue).options(
        selectinload(Issue.assignee),
        selectinload(Issue.reporter),
        selectinload(Issue.release),
    )
    fetch_q = _apply_filters(fetch_q, **filter_kwargs)
    fetch_q = _apply_sort(fetch_q, sort)
    fetch_q = fetch_q.offset((page - 1) * size).limit(size)

    result = await db.execute(fetch_q)
    issues = list(result.scalars().all())

    enriched = await _build_enriched_responses(issues, db)
    return IssueListResponse(items=enriched, total=total, page=page, size=size)


@router.get("/export", summary="Export issues as CSV")
async def export_issues(
    project_id: Optional[uuid.UUID] = Query(None),
    release_id: Optional[uuid.UUID] = Query(None),
    status: Optional[IssueStatus] = Query(None),
    severity: Optional[IssueSeverity] = Query(None),
    assignee_id: Optional[uuid.UUID] = Query(None),
    is_regression: Optional[bool] = Query(None),
    is_release_blocker: Optional[bool] = Query(None),
    unassigned: Optional[bool] = Query(None),
    labels: Optional[List[str]] = Query(None),
    sort: str = Query("newest"),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Export all matching issues as a CSV file (no pagination)."""
    filter_kwargs = dict(
        project_id=project_id,
        release_id=release_id,
        status=status,
        severity=severity,
        assignee_id=assignee_id,
        is_regression=is_regression,
        is_release_blocker=is_release_blocker,
        unassigned=unassigned,
        labels=labels,
        search=search,
    )

    fetch_q = select(Issue).options(
        selectinload(Issue.assignee),
        selectinload(Issue.reporter),
        selectinload(Issue.release),
    )
    fetch_q = _apply_filters(fetch_q, **filter_kwargs)
    fetch_q = _apply_sort(fetch_q, sort)

    result = await db.execute(fetch_q)
    issues = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Issue #", "Issue ID", "Title", "Severity", "Status", "Assignee", "Reporter",
        "Release", "Labels", "Release Blocker", "Regression", "Created At", "Updated At",
    ])
    for issue in issues:
        writer.writerow([
            issue.issue_number,
            str(issue.id),
            issue.title,
            issue.severity,
            issue.status,
            issue.assignee.name if issue.assignee else "",
            issue.reporter.name if issue.reporter else "",
            issue.release.version if issue.release else "",
            ", ".join(issue.labels or []),
            "Yes" if issue.is_release_blocker else "No",
            "Yes" if issue.is_regression else "No",
            issue.created_at.isoformat(),
            issue.updated_at.isoformat(),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="issues.csv"'},
    )


@router.get("/by-number/{issue_number}", response_model=IssueResponse, summary="Get issue by number")
async def get_issue_by_number(
    issue_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Return a single issue by its global issue_number (e.g. the number in issue-10)."""
    result = await db.execute(
        select(Issue).options(
            selectinload(Issue.assignee),
            selectinload(Issue.reporter),
            selectinload(Issue.release),
        ).where(Issue.issue_number == issue_number)
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    enriched = await _build_enriched_responses([issue], db)
    return enriched[0]


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
        db, issue_id, payload.assignee_id, payload.severity, current_user,
        labels=payload.labels, is_release_blocker=payload.is_release_blocker,
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
