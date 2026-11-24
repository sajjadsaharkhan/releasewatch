"""Support channel outbox (slice 21, PRD v3.1 §8.11, FR-71).

The one deliberate exception to "everything goes through ``fan_out``": an inbox
row belongs to a user, and a chat topic is not a user. A row is one post waiting
to be sent (``pending``), sent, or given up on (``failed``).
"""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SupportChannelPost(Base):
    __tablename__ = "support_channel_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=True,
    )
    batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: new_report | status | batch | return_requested | return_confirmed | return_dismissed
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    first_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"),
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    not_before: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
