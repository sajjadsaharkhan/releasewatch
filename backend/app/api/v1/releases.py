"""Releases API router.

Provides cross-project release list and CRUD operations.
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.release import Release, GoNogoStatus
from app.db.models.issue import Issue, IssueStatus, IssueSeverity
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.release import (
    AnalyticsCycleRow,
    GoNogoRequest,
    ReleaseAnalyticsResponse,
    ReleaseCreate,
    ReleaseListResponse,
    ReleaseResponse,
    ReleaseUpdate,
)

router = APIRouter()


async def _get_release_or_404(db: AsyncSession, release_id: int) -> Release:
    """Get a release by ID or raise 404."""
    result = await db.execute(select(Release).where(Release.id == release_id))
    release = result.scalar_one_or_none()
    if release is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Release not found"
        )
    return release


async def _add_release_metrics(db: AsyncSession, release: Release) -> dict:
    """Add computed metrics to a release dict."""
    # Count total issues for this release
    total_result = await db.execute(
        select(func.count()).where(Issue.release_id == release.id)
    )
    total_issues = total_result.scalar() or 0

    # Count open issues (not fixed, verified, or closed)
    open_result = await db.execute(
        select(func.count())
        .where(Issue.release_id == release.id)
        .where(Issue.status.notin_([IssueStatus.fixed, IssueStatus.verified, IssueStatus.closed]))
    )
    open_issues = open_result.scalar() or 0

    # Count blockers
    blocker_result = await db.execute(
        select(func.count())
        .where(Issue.release_id == release.id)
        .where(Issue.severity == IssueSeverity.blocker)
        .where(Issue.status.notin_([IssueStatus.fixed, IssueStatus.verified, IssueStatus.closed]))
    )
    blockers = blocker_result.scalar() or 0

    # Count fixed/verified issues
    fixed_result = await db.execute(
        select(func.count())
        .where(Issue.release_id == release.id)
        .where(Issue.status.in_([IssueStatus.fixed, IssueStatus.verified]))
    )
    fixed_issues = fixed_result.scalar() or 0

    return {
        "open_issues": open_issues,
        "blocker_count": blockers,
        "total_issues": total_issues,
        "fixed_issues": fixed_issues,
    }


async def _release_to_response(
    db: AsyncSession, release: Release
) -> ReleaseResponse:
    """Convert a Release ORM to ReleaseResponse with metrics."""
    metrics = await _add_release_metrics(db, release)

    # Build the response data
    data = {
        "id": release.id,
        "project_id": release.project_id,
        "version": release.version,
        "description": release.description,
        "status": release.status,
        "target_date": release.target_date,
        "staging_url": release.staging_url,
        "go_nogo_status": release.go_nogo_status,
        "go_nogo_note": release.go_nogo_note,
        "go_nogo_by_id": release.go_nogo_by_id,
        "go_nogo_at": release.go_nogo_at,
        "created_by_id": release.created_by_id,
        "created_at": release.created_at,
        "updated_at": release.updated_at,
        **metrics,
    }
    return ReleaseResponse(**data)


@router.get("", response_model=ReleaseListResponse, summary="List all releases")
async def list_releases(
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReleaseListResponse:
    """Return all releases across all projects, most recent first."""
    query = select(Release).order_by(Release.created_at.desc())

    if project_id:
        query = query.where(Release.project_id == project_id)

    if status:
        query = query.where(Release.status == status)

    result = await db.execute(query)
    releases = result.scalars().all()

    # Build responses with metrics
    release_responses = [
        await _release_to_response(db, release) for release in releases
    ]

    return ReleaseListResponse(releases=release_responses, total=len(release_responses))


@router.post(
    "",
    response_model=ReleaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a release",
)
async def create_release(
    payload: ReleaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReleaseResponse:
    """Create a new release."""
    # Verify project exists
    from app.db.models.project import Project

    project_result = await db.execute(
        select(Project).where(Project.id == payload.project_id)
    )
    project = project_result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {payload.project_id} not found",
        )

    release = Release(
        project_id=payload.project_id,
        version=payload.version,
        description=payload.description,
        target_date=payload.target_date,
        staging_url=payload.staging_url,
        created_by_id=current_user.id,
    )
    db.add(release)
    await db.commit()
    await db.refresh(release)
    return await _release_to_response(db, release)


@router.get("/{release_id}", response_model=ReleaseResponse, summary="Get a release")
async def get_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReleaseResponse:
    """Return a single release by ID."""
    release = await _get_release_or_404(db, release_id)
    return await _release_to_response(db, release)


@router.patch(
    "/{release_id}",
    response_model=ReleaseResponse,
    summary="Update release metadata",
)
async def update_release(
    release_id: int,
    payload: ReleaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReleaseResponse:
    """Partially update a release (status, staging URL, description, target date)."""
    release = await _get_release_or_404(db, release_id)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(release, field, value)
    db.add(release)
    await db.commit()
    await db.refresh(release)
    return await _release_to_response(db, release)


@router.get(
    "/{release_id}/analytics",
    response_model=ReleaseAnalyticsResponse,
    summary="Cycle-accurate analytics for a release",
)
async def get_release_analytics(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReleaseAnalyticsResponse:
    """Return all issue cycles for a release so the frontend can compute
    accurate per-iteration MTTF / MTTV / MTTT and regression rate.

    Each row carries the parent issue's severity and labels so the caller
    can group/filter without extra requests.
    """
    from app.db.models.issue_cycle import IssueCycle

    release = await _get_release_or_404(db, release_id)

    # Fetch all cycles joined to their parent issue
    rows = await db.execute(
        select(IssueCycle, Issue)
        .join(Issue, IssueCycle.issue_id == Issue.id)
        .where(Issue.release_id == release.id)
        .order_by(IssueCycle.issue_id, IssueCycle.cycle_number)
    )
    pairs = rows.all()

    # Aggregate totals
    issue_ids = {issue.id for _, issue in pairs}
    total_issues = len(issue_ids)

    verified_q = await db.execute(
        select(func.count(Issue.id))
        .where(Issue.release_id == release.id)
        .where(Issue.status == IssueStatus.verified)
    )
    verified_issues = verified_q.scalar_one()

    regression_q = await db.execute(
        select(func.count(Issue.id))
        .where(Issue.release_id == release.id)
        .where(Issue.is_regression.is_(True))
    )
    regression_count = regression_q.scalar_one()

    cycles = [
        AnalyticsCycleRow(
            issue_id=cycle.issue_id,
            issue_severity=getattr(issue.severity, "value", issue.severity),
            issue_labels=issue.labels or [],
            cycle_number=cycle.cycle_number,
            is_regression_cycle=cycle.cycle_number > 1,
            triaged_at=cycle.triaged_at,
            fixed_at=cycle.fixed_at,
            verified_at=cycle.verified_at,
            time_to_triage_h=cycle.time_to_triage_h,
            time_to_fix_h=cycle.time_to_fix_h,
            time_to_verify_h=cycle.time_to_verify_h,
        )
        for cycle, issue in pairs
    ]

    return ReleaseAnalyticsResponse(
        total_issues=total_issues,
        verified_issues=verified_issues,
        regression_count=regression_count,
        cycles=cycles,
    )


@router.post(
    "/{release_id}/approve",
    response_model=ReleaseResponse,
    summary="Approve a release",
)
async def approve_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReleaseResponse:
    """Mark a release as approved for production."""
    release = await _get_release_or_404(db, release_id)
    release.go_nogo_status = GoNogoStatus.approved
    release.go_nogo_by_id = current_user.id
    release.go_nogo_at = datetime.now(tz=timezone.utc)
    db.add(release)
    await db.commit()
    await db.refresh(release)
    return await _release_to_response(db, release)


@router.post(
    "/{release_id}/block",
    response_model=ReleaseResponse,
    summary="Block a release",
)
async def block_release(
    release_id: int,
    payload: GoNogoRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReleaseResponse:
    """Block a release from production with a reason."""
    release = await _get_release_or_404(db, release_id)
    release.go_nogo_status = GoNogoStatus.blocked
    release.go_nogo_note = payload.note
    release.go_nogo_by_id = current_user.id
    release.go_nogo_at = datetime.now(tz=timezone.utc)
    release.status = "blocked"
    db.add(release)
    await db.commit()
    await db.refresh(release)
    return await _release_to_response(db, release)
