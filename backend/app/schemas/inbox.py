"""Inbox notification schemas."""

from datetime import datetime
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.db.models.inbox_item import InboxEventType


class ActorInfo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    avatar_color: str
    avatar_url: Optional[str] = None


class InboxItemResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    id: uuid.UUID
    type: InboxEventType
    read: bool
    actor: Optional[ActorInfo] = None
    issue_id: Optional[str] = None   # "issue-{number}" format
    issue_title: Optional[str] = None
    created_at: datetime


class InboxListResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    items: list[InboxItemResponse]
    total: int
    page: int
    size: int
    unread_count: int


class UnreadCountResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    unread_count: int
