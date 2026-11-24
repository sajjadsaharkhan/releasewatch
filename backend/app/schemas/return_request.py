"""Return request schemas (slice 20, PRD v3.1 §8.10)."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.attachment import PendingAttachment
from app.schemas.issue import (
    PendingReturnRequest, RequiredComment, ReturnRequestEntryResponse, UserSummary,
)

__all__ = ["PendingReturnRequest", "ReturnRequestEntryResponse"]


class ReturnRequestCreate(BaseModel):
    """``POST /issues/{id}/return-requests`` — the comment is required (FR-68)."""

    comment: RequiredComment
    pending_attachments: list[PendingAttachment] = Field(default_factory=list)


class ReturnRequestDismiss(BaseModel):
    """``POST /return-requests/{id}/dismiss`` — an empty comment is 422 ``reason_required``."""

    comment: str | None = None


class ReturnRequestResponse(BaseModel):
    id: int
    issue_id: int
    status: str
    requested_by: UserSummary | None = None
    requested_at: datetime
    start_comment_id: int | None = None
    entries: list[ReturnRequestEntryResponse] = Field(default_factory=list)
    decided_by: UserSummary | None = None
    decided_at: datetime | None = None
    decision_comment_id: int | None = None
    #: A confirm that found the item no longer Done closes the request with no effect.
    item_already_returned: bool = False


class ReturnRequestItemCard(BaseModel):
    id: int
    issue_number: int
    key: str
    title: str
    status: str
    project_id: int
    release_id: int | None = None
    release_version: str | None = None
    container_kind: str | None = None
    release_status: str | None = None
    project_slug: str | None = None
    project_name: str | None = None
    assignee_user: UserSummary | None = None
    #: When it reached Done.
    done_at: datetime | None = None


class ReturnRequestFirstComment(BaseModel):
    id: int | None = None
    body: str | None = None
    created_at: datetime | None = None


class ReturnRequestQueueRow(BaseModel):
    id: int
    requested_at: datetime
    issue: ReturnRequestItemCard
    requesters: list[UserSummary] = Field(default_factory=list)
    first_comment: ReturnRequestFirstComment
    entry_count: int


class ReturnRequestQueue(BaseModel):
    items: list[ReturnRequestQueueRow]
    total: int
