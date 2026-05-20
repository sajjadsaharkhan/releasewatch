"""Timeline event schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.issue_timeline import TimelineEventType


class TimelineEventCreate(BaseModel):
    """Payload for POST /issues/{id}/timeline (manual comments only)."""

    body: str = Field(min_length=1, description="Comment body (Markdown supported).")
    is_internal: bool = Field(
        False, description="Internal note — hidden from external stakeholders."
    )


class TimelineEventUpdate(BaseModel):
    """Payload for PATCH /issues/{id}/timeline/{event_id}."""

    body: str = Field(min_length=1)


class TimelineEventResponse(BaseModel):
    """Full timeline event representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    event_type: TimelineEventType
    body: Optional[str] = None
    is_internal: bool
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime


class TimelineListResponse(BaseModel):
    """Paginated timeline list."""

    items: list[TimelineEventResponse]
    total: int
    page: int
    size: int
