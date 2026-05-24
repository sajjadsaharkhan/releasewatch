"""Release schemas."""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.db.models.release import GoNogoStatus, ReleaseStatus


class ReleaseBase(BaseModel):
    version: str = Field(max_length=64, description="Semantic version, e.g. '2.4.1'")
    staging_url: Optional[str] = Field(None, max_length=512)
    description: Optional[str] = Field(None, description="Release description / notes")
    target_date: Optional[datetime] = Field(None, description="Target release date")


class ReleaseCreate(ReleaseBase):
    """Payload for POST /releases."""

    project_id: uuid.UUID = Field(description="Project ID to create the release under")


class ReleaseUpdate(BaseModel):
    """Partial payload for PATCH /releases/{id}."""

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

    id: uuid.UUID
    project_id: uuid.UUID
    version: str
    description: Optional[str] = None
    status: ReleaseStatus
    target_date: Optional[datetime] = None
    staging_url: Optional[str] = None
    go_nogo_status: GoNogoStatus
    go_nogo_note: Optional[str] = None
    go_nogo_by_id: Optional[uuid.UUID] = None
    go_nogo_at: Optional[datetime] = None
    created_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    # Computed metrics for UI (stored with _ suffix to avoid conflicts)
    open_issues: int = Field(default=0, description="Count of open issues in this release")
    blocker_count: int = Field(default=0, description="Count of blocker issues")
    total_issues: int = Field(default=0, description="Total issue count")
    fixed_issues: int = Field(default=0, description="Count of fixed/verified issues")

    # Frontend-friendly aliases
    @computed_field  # type: ignore[misc]
    @property
    def projectId(self) -> uuid.UUID:
        return self.project_id

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
    def goNoGoBy(self) -> Optional[uuid.UUID]:
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
