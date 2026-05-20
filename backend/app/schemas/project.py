"""Project schemas."""

from datetime import datetime
from typing import List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    """Fields shared between create and update."""

    name: str = Field(max_length=255)
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
    description: Optional[str] = None
    default_labels: Optional[List[str]] = None


class ProjectResponse(ProjectBase):
    """Full project representation returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    created_by_id: Optional[uuid.UUID] = None
    archived_at: Optional[datetime] = None
    created_at: datetime
