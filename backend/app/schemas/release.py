"""Release schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.db.models.release import GoNogoStatus, ReleaseStatus


class ReleaseBase(BaseModel):
    version: str = Field(max_length=64, description="Semantic version, e.g. '2.4.1'")
    staging_url: Optional[str] = Field(None, max_length=512)
    description: Optional[str] = Field(None, description="Release description / notes")
    target_date: Optional[datetime] = Field(None, description="Target release date")


class ReleaseCreate(ReleaseBase):
    """Payload for POST /releases."""

    project_id: int = Field(description="Project ID to create the release under")


class ReleaseUpdate(BaseModel):
    """Partial payload for PATCH /releases/{id}."""

    version: Optional[str] = Field(None, max_length=64)
    status: Optional[ReleaseStatus] = None
    staging_url: Optional[str] = Field(None, max_length=512)
    description: Optional[str] = None
    target_date: Optional[datetime] = None


class GoNogoRequest(BaseModel):
    """Payload for POST /releases/{id}/approve."""

    decision: GoNogoStatus  # approved | blocked
    note: Optional[str] = None


class ReleaseResponse(ReleaseBase):
    """Full release representation with computed metrics."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    version: str
    description: Optional[str] = None
    status: ReleaseStatus
    target_date: Optional[datetime] = None
    staging_url: Optional[str] = None
    go_nogo_status: GoNogoStatus
    go_nogo_note: Optional[str] = None
    go_nogo_by_id: Optional[int] = None
    go_nogo_at: Optional[datetime] = None
    created_by_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    # Computed metrics for UI (stored with _ suffix to avoid conflicts)
    open_issues: int = Field(default=0, description="Count of open issues in this release")
    blocker_count: int = Field(default=0, description="Count of blocker issues")
    total_issues: int = Field(default=0, description="Total issue count")
    fixed_issues: int = Field(default=0, description="Count of fixed/verified issues")
    project_name: Optional[str] = None

    # Frontend-friendly aliases
    @computed_field  # type: ignore[misc]
    @property
    def projectId(self) -> int:
        return self.project_id

    @computed_field  # type: ignore[misc]
    @property
    def projectName(self) -> Optional[str]:
        return self.project_name

    @computed_field  # type: ignore[misc]
    @property
    def createdAt(self) -> datetime:
        return self.created_at

    @computed_field  # type: ignore[misc]
    @property
    def targetDate(self) -> Optional[datetime]:
        return self.target_date

    @computed_field  # type: ignore[misc]
    @property
    def goNoGo(self) -> Optional[str]:
        return self.go_nogo_status.value if self.go_nogo_status else None

    @computed_field  # type: ignore[misc]
    @property
    def goNoGoBy(self) -> Optional[int]:
        return self.go_nogo_by_id

    @computed_field  # type: ignore[misc]
    @property
    def openIssues(self) -> int:
        return self.open_issues

    @computed_field  # type: ignore[misc]
    @property
    def blockers(self) -> int:
        return self.blocker_count

    @computed_field  # type: ignore[misc]
    @property
    def totalIssues(self) -> int:
        return self.total_issues

    @computed_field  # type: ignore[misc]
    @property
    def fixedIssues(self) -> int:
        return self.fixed_issues


class ReleaseListResponse(BaseModel):
    """Paginated response for release list."""

    releases: list[ReleaseResponse]
    total: int


class AnalyticsCycleRow(BaseModel):
    """Flattened cycle row returned by the release analytics endpoint.

    Carries enough issue context (severity, labels) for the frontend to group
    and filter without additional requests.
    """

    issue_id: int
    issue_severity: str
    issue_labels: List[str]
    cycle_number: int
    is_regression_cycle: bool
    triaged_at: Optional[datetime] = None
    fixed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    time_to_triage_h: Optional[float] = None
    time_to_fix_h: Optional[float] = None
    time_to_verify_h: Optional[float] = None


class ReleaseAnalyticsResponse(BaseModel):
    """Aggregated analytics payload for a single release."""

    total_issues: int
    verified_issues: int
    regression_count: int
    cycles: List[AnalyticsCycleRow]
