"""Release schemas."""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.db.models.release import GoNogoStatus, ReleaseKind, ReleaseStatus
from app.schemas.issue import IssueResponse, UserSummary


class ReleaseBase(BaseModel):
    version: str = Field(max_length=64, description="Semantic version, e.g. '2.4.1'")
    staging_url: Optional[str] = Field(None, max_length=512)
    description: Optional[str] = Field(None, description="Release description / notes")
    target_date: Optional[datetime] = Field(None, description="Target ship date")
    code_freeze_date: Optional[date] = Field(None, description="When QA starts (optional)")


class ReleaseCreate(ReleaseBase):
    """Payload for POST /releases."""

    project_id: int = Field(description="Project ID to create the release under")


class ProjectReleaseCreate(ReleaseBase):
    """Payload for POST /projects/{id}/releases (FR-49) — starts in Planning."""


class ReleaseStatusRequest(BaseModel):
    """POST /releases/{id}/status — a manual lifecycle move (FR-50)."""

    to: ReleaseStatus


class ShipRequest(BaseModel):
    """POST /releases/{id}/ship — the caller confirms having seen the notice."""

    confirm: Literal[True]


class GoNogoDecision(BaseModel):
    status: GoNogoStatus
    note: Optional[str] = None
    by_id: Optional[int] = None
    at: Optional[datetime] = None


class ShipPreviewResponse(BaseModel):
    """GET /releases/{id}/ship-preview (FR-53, AC-60)."""

    go_nogo: GoNogoDecision
    #: Not-Done items by board status.
    not_done: Dict[str, int]
    #: Every item that will move to the backlog (triage statuses included).
    total_not_done: int
    done: int


class ReleaseEventResponse(BaseModel):
    """One entry of the release Activity tab (FR-51)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    actor: Optional[UserSummary] = None
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime


class ReleaseActivityResponse(BaseModel):
    events: List[ReleaseEventResponse]


class BoardColumn(BaseModel):
    status: str
    items: List[IssueResponse]


class ReleaseBoardResponse(BaseModel):
    """GET /releases/{id}/board — five columns; ``done_from``/``done_to`` bound
    only the Done column (FR-47)."""

    columns: List[BoardColumn]
    done_from: Optional[datetime] = None
    done_to: Optional[datetime] = None


class ReleaseItemsResponse(BaseModel):
    items: List[IssueResponse]
    total: int


class ReleaseUpdate(BaseModel):
    """Partial payload for PATCH /releases/{id}."""

    version: Optional[str] = Field(None, max_length=64)
    status: Optional[ReleaseStatus] = None
    staging_url: Optional[str] = Field(None, max_length=512)
    description: Optional[str] = None
    target_date: Optional[datetime] = None
    code_freeze_date: Optional[date] = None


class GoNogoRequest(BaseModel):
    """Payload for POST /releases/{id}/approve."""

    decision: GoNogoStatus  # approved | blocked
    note: Optional[str] = None


class ReleaseResponse(ReleaseBase):
    """Full release representation with computed metrics."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    kind: ReleaseKind = ReleaseKind.release
    version: str
    description: Optional[str] = None
    #: Null for the Stream, which has no lifecycle (08a).
    status: Optional[ReleaseStatus] = None
    target_date: Optional[datetime] = None
    code_freeze_date: Optional[date] = None
    released_at: Optional[datetime] = None
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
    project_slug: Optional[str] = None

    # Slice 09 — computed on read, never stored.
    #: Items by status, every status included.
    counts: Dict[str, int] = Field(default_factory=dict)
    #: Done ÷ non-cancelled items (BR-47); null with no non-cancelled item or on the Stream.
    progress: Optional[float] = None
    #: BR-48 — never on the Stream, an undated, a Released or a Cancelled release.
    is_overdue: bool = False
    #: Lifecycle moves the caller may make now (Released is Ship's, never listed).
    allowed_transitions: List[str] = Field(default_factory=list)
    #: Of ``manage_releases``, ``ship_release``, ``go_nogo`` — empty once final.
    allowed_actions: List[str] = Field(default_factory=list)

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

    Carries enough issue context (priority, labels) for the frontend to group
    and filter without additional requests.
    """

    issue_id: int
    issue_priority: str | None = None
    issue_labels: List[str]
    cycle_number: int
    #: Why the cycle started (08a): planned | review | release_qa | production.
    start_reason: str = "planned"
    #: One of the cycles Phase 1 counted as a regression (review / release_qa, bug, release).
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
