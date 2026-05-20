"""Reports API — release reports, contributions, time-to-fix, regressions, dashboard."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.services.report_service import ReportService

router = APIRouter()
_svc = ReportService()


@router.get("/releases/{release_id}")
async def get_release_report(
    release_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full release report: metrics, charts, team breakdown, go/no-go status."""
    return await _svc.get_release_report(db, release_id)


@router.get("/contributions")
async def get_contributions(
    release_id: str | None = Query(None),
    role: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Member contribution metrics: reporter and solver leaderboards."""
    filters = {"release_id": release_id, "role": role, "date_from": date_from, "date_to": date_to}
    return await _svc.get_contributions(db, filters)


@router.get("/contributions/time-to-fix")
async def get_time_to_fix(
    release_id: str | None = Query(None),
    role: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """MTTF by severity with mean, median, fastest, slowest percentiles."""
    filters = {"release_id": release_id, "role": role}
    return await _svc.get_time_to_fix(db, filters)


@router.get("/regressions")
async def get_regressions(
    project_id: str | None = Query(None),
    n_releases: int = Query(6, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regression analysis: component fragility, recurrence matrix."""
    return await _svc.get_regressions(db, project_id, n_releases)


@router.get("/dashboard")
async def get_dashboard(
    project_ids: list[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """CTO dashboard aggregates: open blockers, criticals, regression rate, activity feed."""
    return await _svc.get_dashboard(db, project_ids or [])
