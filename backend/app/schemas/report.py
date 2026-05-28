"""Report schemas — analytics and dashboard response shapes."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SeverityBreakdown(BaseModel):
    blocker: int = 0
    critical: int = 0
    major: int = 0
    minor: int = 0
    enhancement: int = 0


class StatusBreakdown(BaseModel):
    new: int = 0
    triaged: int = 0
    in_progress: int = 0
    fixed: int = 0
    verified: int = 0
    closed: int = 0
    regression: int = 0


class ReleaseReportResponse(BaseModel):
    """Aggregate stats for a single release — GET /reports/releases/{release_id}."""

    release_id: int
    version: str
    project_name: str
    total_issues: int
    open_issues: int
    blocker_count: int
    regression_count: int
    go_nogo_status: str
    severity_breakdown: SeverityBreakdown
    status_breakdown: StatusBreakdown
    avg_time_to_triage_h: Optional[float] = None
    avg_time_to_fix_h: Optional[float] = None
    avg_time_to_verify_h: Optional[float] = None


class ContributorStat(BaseModel):
    user_id: int
    name: str
    username: str
    issues_filed: int = 0
    issues_fixed: int = 0
    issues_verified: int = 0


class ContributionsResponse(BaseModel):
    """Team contribution summary — GET /reports/contributions."""

    contributors: List[ContributorStat]
    period_start: Optional[str] = None
    period_end: Optional[str] = None


class TimeToFixEntry(BaseModel):
    user_id: int
    name: str
    avg_time_to_fix_h: float
    sample_size: int


class TimeToFixResponse(BaseModel):
    """Developer time-to-fix leaderboard."""

    entries: List[TimeToFixEntry]


class RegressionEntry(BaseModel):
    issue_id: int
    issue_number: int
    title: str
    regression_count: int
    last_regression_at: Optional[str] = None


class RegressionsResponse(BaseModel):
    """Regression frequency report — GET /reports/regressions."""

    project_id: int
    entries: List[RegressionEntry]


class DashboardResponse(BaseModel):
    """Multi-project dashboard summary — GET /reports/dashboard."""

    total_open_issues: int
    total_blockers: int
    total_regressions: int
    projects: List[Dict[str, Any]]
