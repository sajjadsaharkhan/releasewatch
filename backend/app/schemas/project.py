"""Project schemas."""

from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ProjectBase(BaseModel):
    """Fields shared between create and update."""

    name: str = Field(max_length=255)
    color: str = Field(default="#6366f1", pattern=r"^#[0-9A-Fa-f]{6}$")
    description: Optional[str] = None
    default_labels: List[str] = Field(default_factory=list)


class ProjectCreate(ProjectBase):
    """Payload for POST /projects."""

    slug: str = Field(
        max_length=128,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        description="URL-safe identifier (lowercase, hyphens only).",
    )


class ProjectUpdate(BaseModel):
    """Partial payload for PATCH /projects/{slug}."""

    name: Optional[str] = Field(None, max_length=255)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    description: Optional[str] = None
    default_labels: Optional[List[str]] = None


class ProjectArchiveRequest(BaseModel):
    """Payload for POST /projects/{id}/archive."""

    archive: bool = Field(default=True, description="True to archive, False to restore")


class ProjectResponse(ProjectBase):
    """Full project representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    created_by_id: Optional[uuid.UUID] = None
    archived_at: Optional[datetime] = None
    created_at: datetime

    @computed_field  # type: ignore[misc]
    @property
    def archived(self) -> bool:
        """Computed property: true if archived_at is set."""
        return self.archived_at is not None

    @computed_field  # type: ignore[misc]
    @property
    def desc(self) -> Optional[str]:
        """Alias for description to match frontend naming."""
        return self.description
