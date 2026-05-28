"""Issue schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.issue import IssueSeverity, IssueStatus
from app.db.models.user import UserRole
from app.schemas.attachment import PendingAttachment


class UserSummary(BaseModel):
    """Minimal user info embedded in issue responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: str
    role: UserRole
    avatar_url: Optional[str] = None
    avatar_color: str


class LabelDetail(BaseModel):
    """Label info embedded in issue responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    color: str


# Reproduction step structure (stored as JSON in the Issue model)
class ReproductionStep(BaseModel):
    """A single reproduction step."""
    step_order: int = Field(ge=1, description="Step number (1-based)")
    description: str = Field(description="What to do in this step")
    expected_result: Optional[str] = Field(None, description="What should happen")
    actual_result: Optional[str] = Field(None, description="What actually happened")


class IssueBase(BaseModel):
    title: str = Field(max_length=512)
    description: Optional[str] = None
    severity: IssueSeverity = IssueSeverity.minor
    labels: List[str] = Field(default_factory=list)
    is_release_blocker: bool = False
    environment_browser: Optional[str] = Field(None, max_length=128)
    environment_os: Optional[str] = Field(None, max_length=128)
    environment_build_hash: Optional[str] = Field(None, max_length=64)
    environment_staging_url: Optional[str] = Field(None, max_length=512)
    environment_name: Optional[str] = Field(
        None, pattern=r'^(production|staging|development|local|qa)$'
    )
    curl_command: Optional[str] = None


class IssueCreate(IssueBase):
    """Payload for POST /issues."""

    release_id: int
    reproduction_steps: List[ReproductionStep] = Field(default_factory=list)
    pending_attachments: List[PendingAttachment] = Field(default_factory=list)


class IssueUpdate(BaseModel):
    """Partial update payload for PATCH /issues/{id}."""

    title: Optional[str] = Field(None, max_length=512)
    description: Optional[str] = None
    severity: Optional[IssueSeverity] = None
    status: Optional[IssueStatus] = None
    labels: Optional[List[str]] = None
    is_release_blocker: Optional[bool] = None
    assignee_id: Optional[Any] = None
    release_id: Optional[Any] = None
    environment_browser: Optional[str] = None
    environment_os: Optional[str] = None
    environment_build_hash: Optional[str] = None
    environment_staging_url: Optional[str] = None
    environment_name: Optional[str] = Field(
        None, pattern=r'^(production|staging|development|local|qa)$'
    )
    curl_command: Optional[str] = None
    reproduction_steps: Optional[List[Any]] = None


class TriageRequest(BaseModel):
    """Payload for POST /issues/{id}/triage."""

    assignee_id: int
    severity: IssueSeverity
    labels: Optional[List[str]] = None
    is_release_blocker: Optional[bool] = None
    note: Optional[str] = None


class FixRequest(BaseModel):
    """Payload for POST /issues/{id}/fix."""

    mr_url: Optional[str] = Field(None, max_length=512, description="GitLab / GitHub MR link")
    note: Optional[str] = None


class VerifyRequest(BaseModel):
    """Payload for POST /issues/{id}/verify."""

    outcome: str = Field(pattern=r"^(pass|fail|partial)$")
    note: Optional[str] = None


class DuplicateRequest(BaseModel):
    """Payload for POST /issues/{id}/duplicate."""

    parent_id: int


class IssueResponse(IssueBase):
    """Full issue representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_number: int
    project_id: int
    project_name: Optional[str] = None
    release_id: int
    release_version: Optional[str] = None
    status: IssueStatus
    reporter_id: Optional[int] = None
    assignee_id: Optional[int] = None
    assignee_user: Optional[UserSummary] = None
    reporter_user: Optional[UserSummary] = None
    labels_detail: List[LabelDetail] = Field(default_factory=list)
    is_regression: bool
    regression_count: int
    environment_name: Optional[str] = None
    parent_issue_id: Optional[int] = None
    time_to_triage_h: Optional[float] = None
    time_to_fix_h: Optional[float] = None
    time_to_verify_h: Optional[float] = None
    filed_at: Optional[datetime] = None
    triaged_at: Optional[datetime] = None
    fixed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    reproduction_steps: List[ReproductionStep] = Field(default_factory=list)


class IssueListResponse(BaseModel):
    """Paginated issue list wrapper."""

    items: List[IssueResponse]
    total: int
    page: int
    size: int


class IssueCycleResponse(BaseModel):
    """Per-iteration timing metrics for one issue workflow pass."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    cycle_number: int
    is_regression_cycle: bool = False
    cycle_start_at: datetime
    triaged_at: Optional[datetime] = None
    fixed_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    time_to_triage_h: Optional[float] = None
    time_to_fix_h: Optional[float] = None
    time_to_verify_h: Optional[float] = None

    @classmethod
    def from_orm_with_flag(cls, cycle) -> "IssueCycleResponse":
        obj = cls.model_validate(cycle)
        obj.is_regression_cycle = cycle.cycle_number > 1
        return obj


class RegressionHistoryResponse(BaseModel):
    """A single regression event for an issue."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    regression_number: int
    detected_at: datetime
    release_id: int
    release_version: Optional[str] = None
    detected_by: Optional[UserSummary] = None
    previous_fix_by: Optional[UserSummary] = None
