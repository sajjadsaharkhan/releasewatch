"""Issue schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.issue import IssueSeverity, IssueStatus


class ReproductionStepCreate(BaseModel):
    step_order: int = Field(ge=1)
    description: str
    expected_result: Optional[str] = None
    actual_result: Optional[str] = None


class ReproductionStepResponse(ReproductionStepCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    issue_id: uuid.UUID


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
    curl_command: Optional[str] = None


class IssueCreate(IssueBase):
    """Payload for POST /issues."""

    release_id: uuid.UUID
    reproduction_steps: List[ReproductionStepCreate] = Field(default_factory=list)


class IssueUpdate(BaseModel):
    """Partial update payload for PATCH /issues/{id}."""

    title: Optional[str] = Field(None, max_length=512)
    description: Optional[str] = None
    severity: Optional[IssueSeverity] = None
    labels: Optional[List[str]] = None
    is_release_blocker: Optional[bool] = None
    environment_browser: Optional[str] = None
    environment_os: Optional[str] = None
    environment_build_hash: Optional[str] = None
    environment_staging_url: Optional[str] = None
    curl_command: Optional[str] = None


class TriageRequest(BaseModel):
    """Payload for POST /issues/{id}/triage."""

    assignee_id: uuid.UUID
    severity: IssueSeverity
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

    parent_id: uuid.UUID


class IssueResponse(IssueBase):
    """Full issue representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_number: int
    project_id: uuid.UUID
    release_id: uuid.UUID
    status: IssueStatus
    reporter_id: Optional[uuid.UUID] = None
    assignee_id: Optional[uuid.UUID] = None
    is_regression: bool
    regression_count: int
    parent_issue_id: Optional[uuid.UUID] = None
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
    reproduction_steps: List[ReproductionStepResponse] = Field(default_factory=list)


class IssueListResponse(BaseModel):
    """Paginated issue list wrapper."""

    items: List[IssueResponse]
    total: int
    page: int
    size: int
