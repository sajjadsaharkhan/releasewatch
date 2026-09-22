"""Issue schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.issue import IssueCancelReason, IssueSeverity, IssueStatus
from app.db.models.user import UserRole
from app.schemas.attachment import PendingAttachment


class UserSummary(BaseModel):
    """Minimal user info embedded in issue responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    username: str
    role: UserRole
    avatar_url: str | None = None
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
    expected_result: str | None = Field(None, description="What should happen")
    actual_result: str | None = Field(None, description="What actually happened")


class IssueBase(BaseModel):
    title: str = Field(max_length=512)
    description: str | None = None
    severity: IssueSeverity | None = None
    labels: list[str] = Field(default_factory=list)
    is_release_blocker: bool = False
    environment_browser: str | None = Field(None, max_length=128)
    environment_os: str | None = Field(None, max_length=128)
    environment_build_hash: str | None = Field(None, max_length=64)
    environment_staging_url: str | None = Field(None, max_length=512)
    environment_name: str | None = Field(
        None, pattern=r'^(production|staging|development|local|qa)$'
    )
    curl_command: str | None = None


class IssueCreate(IssueBase):
    """Payload for POST /issues."""

    release_id: int
    reproduction_steps: list[ReproductionStep] = Field(default_factory=list)
    pending_attachments: list[PendingAttachment] = Field(default_factory=list)


class IssueUpdate(BaseModel):
    """Partial update payload for PATCH /issues/{id}."""

    title: str | None = Field(None, max_length=512)
    description: str | None = None
    severity: IssueSeverity | None = None
    status: IssueStatus | None = None
    labels: list[str] | None = None
    is_release_blocker: bool | None = None
    assignee_id: Any | None = None
    release_id: Any | None = None
    project_id: Any | None = None
    environment_browser: str | None = None
    environment_os: str | None = None
    environment_build_hash: str | None = None
    environment_staging_url: str | None = None
    environment_name: str | None = Field(
        None, pattern=r'^(production|staging|development|local|qa)$'
    )
    curl_command: str | None = None
    reproduction_steps: list[Any] | None = None
    cancel_reason: IssueCancelReason | None = Field(
        None, description="Required when status is set to cancelled."
    )


class TransitionRequest(BaseModel):
    """Payload for POST /issues/{id}/transition."""

    to: IssueStatus
    reason: str | None = None
    comment: str | None = None
    cancel_reason: IssueCancelReason | None = None


class BlockedTransition(BaseModel):
    """A target status that is normally reachable but refused for this actor/item."""

    to: str
    code: str
    detail: str


class TriageRequest(BaseModel):
    """Payload for POST /issues/{id}/triage."""

    assignee_id: int
    severity: IssueSeverity
    labels: list[str] | None = None
    is_release_blocker: bool | None = None
    note: str | None = None


class FixRequest(BaseModel):
    """Payload for POST /issues/{id}/fix."""

    mr_url: str | None = Field(None, max_length=512, description="GitLab / GitHub MR link")
    note: str | None = None


class VerifyRequest(BaseModel):
    """Payload for POST /issues/{id}/verify."""

    outcome: str = Field(pattern=r"^(pass|fail|partial)$")
    note: str | None = None


class DuplicateRequest(BaseModel):
    """Payload for POST /issues/{id}/duplicate."""

    parent_id: int


class NeedsClarificationRequest(BaseModel):
    """Payload for POST /issues/{id}/needs-clarification."""

    message: str | None = None


class IssueResponse(IssueBase):
    """Full issue representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_number: int
    project_id: int
    project_name: str | None = None
    release_id: int
    release_version: str | None = None
    status: IssueStatus
    reporter_id: int | None = None
    assignee_id: int | None = None
    assignee_user: UserSummary | None = None
    reporter_user: UserSummary | None = None
    labels_detail: list[LabelDetail] = Field(default_factory=list)
    is_regression: bool
    regression_count: int
    environment_name: str | None = None
    parent_issue_id: int | None = None
    cancel_reason: IssueCancelReason | None = None
    blocked_from_status: str | None = None
    review_requested_by_id: int | None = None
    time_to_triage_h: float | None = None
    time_to_fix_h: float | None = None
    time_to_verify_h: float | None = None
    filed_at: datetime | None = None
    triaged_at: datetime | None = None
    started_at: datetime | None = None
    fixed_at: datetime | None = None
    verified_at: datetime | None = None
    completed_at: datetime | None = None
    closed_at: datetime | None = None
    cancelled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    reproduction_steps: list[ReproductionStep] = Field(default_factory=list)
    project_triage_lead_id: int | None = None
    allowed_transitions: list[str] = Field(default_factory=list)
    blocked_transitions: list[BlockedTransition] = Field(default_factory=list)


class IssueListResponse(BaseModel):
    """Paginated issue list wrapper."""

    items: list[IssueResponse]
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
    triaged_at: datetime | None = None
    fixed_at: datetime | None = None
    verified_at: datetime | None = None
    time_to_triage_h: float | None = None
    time_to_fix_h: float | None = None
    time_to_verify_h: float | None = None

    @classmethod
    def from_orm_with_flag(cls, cycle) -> "IssueCycleResponse":
        obj = cls.model_validate(cycle)
        obj.is_regression_cycle = cycle.cycle_number > 1
        return obj


class TrashIssueResponse(BaseModel):
    """Soft-deleted issue — summary + detail fields returned by GET /issues/trash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_number: int
    title: str
    description: str | None = None
    severity: IssueSeverity | None = None
    status: IssueStatus
    release_id: int
    release_name: str | None = None
    project_id: int
    project_name: str | None = None
    reporter_id: int | None = None
    reporter_name: str | None = None
    reporter_username: str | None = None
    reporter_avatar_color: str | None = None
    reporter_avatar_url: str | None = None
    deleted_at: datetime
    deleted_by_id: int | None = None
    deleted_by_name: str | None = None
    deleted_by_username: str | None = None
    deleted_by_avatar_color: str | None = None
    deleted_by_avatar_url: str | None = None


class RegressionHistoryResponse(BaseModel):
    """A single regression event for an issue."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    regression_number: int
    detected_at: datetime
    release_id: int
    release_version: str | None = None
    detected_by: UserSummary | None = None
    previous_fix_by: UserSummary | None = None
