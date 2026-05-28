"""Timeline event schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.issue_timeline import TimelineEventType
from app.schemas.issue import UserSummary


class TimelineEventCreate(BaseModel):
    """Payload for POST /issues/{id}/timeline (manual comments only)."""

    body: str = Field(min_length=1, description="Comment body (Markdown supported).")
    is_internal: bool = Field(
        False, description="Internal note — hidden from external stakeholders."
    )
    mentioned_user_ids: List[int] = Field(
        default_factory=list,
        description="User IDs @mentioned in this comment.",
    )


class TimelineEventUpdate(BaseModel):
    """Payload for PATCH /issues/{id}/timeline/{event_id}."""

    body: str = Field(min_length=1)


class TimelineEventResponse(BaseModel):
    """Full timeline event representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    actor_id: Optional[int] = None
    actor_user: Optional[UserSummary] = None
    event_type: TimelineEventType
    body: Optional[str] = None
    is_internal: bool
    meta: Optional[Dict[str, Any]] = None
    created_at: datetime

    # Derived from meta — populated by the validator below
    mentioned_user_ids: List[int] = Field(default_factory=list)
    edited_at: Optional[datetime] = None

    @model_validator(mode='after')
    def extract_meta_fields(self) -> 'TimelineEventResponse':
        if self.meta:
            raw_ids = self.meta.get('mentioned_user_ids', [])
            ids = []
            for u in raw_ids:
                try:
                    ids.append(int(u))
                except (ValueError, TypeError):
                    pass
            self.mentioned_user_ids = ids
            if ea := self.meta.get('edited_at'):
                try:
                    self.edited_at = datetime.fromisoformat(ea)
                except (ValueError, TypeError):
                    pass
        return self


class TimelineListResponse(BaseModel):
    """Paginated timeline list."""

    items: list[TimelineEventResponse]
    total: int
    page: int
    size: int
