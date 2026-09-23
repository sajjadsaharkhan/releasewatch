"""Issue schemas."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.db.models.issue import (
    ISSUE_TYPE_KEY_PREFIX,
    TASK_DEFAULT_PRIORITY,
    IssueCancelReason,
    IssueStatus,
    IssueType,
    Priority,
)
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
    priority: Priority | None = None
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
    """Payload for POST /issues.

    ``type`` is fixed at creation (BR-07) and never accepted on PATCH.
    ``project_id`` is always required; ``release_id`` is optional (D7,
    BR-26) but when given must belong to ``project_id`` and to a Product
    project (enforced in ``IssueService.create`` — needs a DB lookup, so it
    isn't a field validator).
    """

    type: IssueType = IssueType.bug
    project_id: int
    release_id: int | None = None
    due_date: date | None = None
    assignee_id: int | None = None
    reproduction_steps: list[ReproductionStep] = Field(default_factory=list)
    pending_attachments: list[PendingAttachment] = Field(default_factory=list)

    @model_validator(mode="after")
    def _type_specific_fields(self) -> "IssueCreate":
        """Cross-field validation, run only after every field is individually
        coerced (``mode="after"``) — a plain ``field_validator`` can't see
        ``self.type`` while validating an inherited ``IssueBase`` field, since
        pydantic validates base-class fields before subclass-only ones. The
        error messages carry the field name first, so a client can still key
        off it even though the loc is the model root.
        """
        if self.type == IssueType.task:
            # A bug may stay unrated until triage; a task starts at medium (BR-16).
            if self.priority is None:
                self.priority = TASK_DEFAULT_PRIORITY
            if self.is_release_blocker:
                raise ValueError("is_release_blocker: tasks cannot be release blockers.")
            if self.curl_command is not None:
                raise ValueError("curl_command: bug-only field.")
            if self.reproduction_steps:
                raise ValueError("reproduction_steps: bug-only field.")
            for field_name in (
                "environment_browser", "environment_os", "environment_build_hash",
                "environment_staging_url", "environment_name",
            ):
                if getattr(self, field_name) is not None:
                    raise ValueError(f"{field_name}: bug-only field.")
        return self


class IssueUpdate(BaseModel):
    """Partial update payload for PATCH /issues/{id}."""

    title: str | None = Field(None, max_length=512)
    description: str | None = None
    priority: Priority | None = None
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
    due_date: date | None = None
    type: Any | None = Field(
        None, description="Rejected — type is immutable once created (BR-07, 409 type_immutable)."
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
    priority: Priority = Field(description="Required to accept a bug (BR-16, AC-16).")
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
    type: IssueType = IssueType.bug
    project_id: int
    project_name: str | None = None
    release_id: int | None = None
    release_version: str | None = None
    status: IssueStatus
    due_date: date | None = None
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

    @computed_field  # type: ignore[misc]
    @property
    def key(self) -> str:
        """Display key, e.g. ``BUG-123`` / ``TASK-124`` — same global sequence as issue_number."""
        return f"{ISSUE_TYPE_KEY_PREFIX[self.type]}-{self.issue_number}"


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
    type: IssueType = IssueType.bug
    title: str
    description: str | None = None
    priority: Priority | None = None
    status: IssueStatus
    release_id: int | None = None
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
