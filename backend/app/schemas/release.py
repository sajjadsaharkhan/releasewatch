"""Release schemas."""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.release import GoNogoStatus, ReleaseStatus


class ReleaseBase(BaseModel):
    version: str = Field(max_length=64, description="Semantic version, e.g. '2.4.1'")
    staging_url: Optional[str] = Field(None, max_length=512)


class ReleaseCreate(ReleaseBase):
    """Payload for POST /projects/{slug}/releases."""
    pass


class ReleaseUpdate(BaseModel):
    """Partial payload for PATCH /projects/{slug}/releases/{version}."""

    status: Optional[ReleaseStatus] = None
    staging_url: Optional[str] = Field(None, max_length=512)


class GoNogoRequest(BaseModel):
    """Payload for POST /projects/{slug}/releases/{version}/go-nogo."""

    decision: GoNogoStatus  # approved | blocked
    note: Optional[str] = None


class ReleaseResponse(ReleaseBase):
    """Full release representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    status: ReleaseStatus
    go_nogo_status: GoNogoStatus
    go_nogo_note: Optional[str] = None
    go_nogo_by_id: Optional[uuid.UUID] = None
    go_nogo_at: Optional[datetime] = None
    created_by_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
