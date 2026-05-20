"""Inbox notification schemas."""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict

from app.db.models.inbox_item import InboxEventType


class InboxItemResponse(BaseModel):
    """A single inbox notification entry."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    issue_id: uuid.UUID
    timeline_id: Optional[uuid.UUID] = None
    event_type: InboxEventType
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime


class InboxListResponse(BaseModel):
    """Paginated inbox."""

    items: list[InboxItemResponse]
    total: int
    page: int
    size: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    """Unread inbox count."""

    unread_count: int
