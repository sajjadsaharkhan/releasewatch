"""InboxItem ORM model — per-user notification feed."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InboxEventType(str, enum.Enum):
    """The kind of event that generated this inbox notification."""

    assigned = "assigned"
    fixed = "fixed"
    comment = "comment"
    mention = "mention"
    regression = "regression"
    blocker_filed = "blocker_filed"
    blocker_cleared = "blocker_cleared"
    status_changed = "status_changed"
    verified = "verified"
    filed = "filed"
    environment_changed = "environment_changed"
    release_changed = "release_changed"
    attachment_added = "attachment_added"
    severity_changed = "severity_changed"
    needs_clarification = "needs_clarification"


class InboxItem(Base):
    """A notification delivered to a specific user's inbox.

    Items are created via fan-out logic in ``InboxFanOutService`` whenever a
    relevant issue event occurs.  Each user has their own copy so that
    ``is_read`` state is independent.
    """

    __tablename__ = "inbox_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timeline_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("issue_timeline.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[InboxEventType] = mapped_column(String(32), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # ── Composite index to speed up unread-count and per-user inbox queries ───
    __table_args__ = (
        Index("ix_inbox_items_user_is_read", "user_id", "is_read"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user = relationship("User", foreign_keys=[user_id], back_populates="inbox_items")
    actor = relationship("User", foreign_keys=[actor_id])
    issue = relationship("Issue", back_populates="inbox_items")
    timeline_event = relationship("IssueTimeline", back_populates="inbox_items")

    def __repr__(self) -> str:
        return f"<InboxItem user={self.user_id} type={self.event_type} read={self.is_read}>"
