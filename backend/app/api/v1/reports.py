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
    project_id: int | None = Query(None),
    release_id: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Member contribution metrics: table rows, segmented chart, and label distribution."""
    filters = {"project_id": project_id, "release_id": release_id, "date_from": date_from, "date_to": date_to}
    return await _svc.get_contributions(db, filters)


@router.get("/contributions/metrics")
async def get_contribution_metrics(
    project_id: int | None = Query(None),
    release_id: int | None = Query(None),
    user_id: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Weekly time-series of regression rate and mean times (triage, fix, verify)."""
    filters = {"project_id": project_id, "release_id": release_id, "user_id": user_id, "date_from": date_from, "date_to": date_to}
    return await _svc.get_contribution_metrics(db, filters)


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
    date_from: str | None = Query(None, description="ISO date YYYY-MM-DD — filter releases created on or after this date"),
    date_to: str | None = Query(None, description="ISO date YYYY-MM-DD — filter releases created on or before this date"),
    label: str | None = Query(None, description="Filter all metrics to issues that have this label name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Regression analysis: KPIs, chart series, team tables, top issues."""
    return await _svc.get_regressions(db, project_id, n_releases, date_from, date_to, label)


@router.get("/dashboard")
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Full dashboard payload: hero metrics, release health, stale items, activity stream."""
    return await _svc.get_dashboard(db, current_user)
