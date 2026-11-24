"""Support channel schemas (slice 21, PRD v3.1 FR-70)."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class SupportChannelUpdate(BaseModel):
    #: Telegram chat id — negative for a group or supergroup.
    chat_id: int
    #: The topic (message thread) id inside a supergroup; null posts to the chat itself.
    thread_id: int | None = Field(None, gt=0)
    enabled: bool = False

    @field_validator("chat_id")
    @classmethod
    def _chat_id_set(cls, v: int) -> int:
        if v == 0:
            raise ValueError("chat_id must be a Telegram chat id")
        return v


class SupportChannelResponse(BaseModel):
    chat_id: int | None = None
    thread_id: int | None = None
    enabled: bool = False
    #: A passing test since the chat or topic last changed — what enabling needs.
    tested: bool = False
    tested_at: datetime | None = None
    pending_posts: int = 0
    failed_posts: int = 0
    last_error: str | None = None


class SupportChannelTestResult(BaseModel):
    ok: bool
    error: str | None = None
