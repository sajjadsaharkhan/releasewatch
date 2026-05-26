"""InboxItem ORM model — per-user notification feed."""

import uuid
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
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
    status_changed = "status_changed"
    verified = "verified"
    filed = "filed"


class InboxItem(Base):
    """A notification delivered to a specific user's inbox.

    Items are created via fan-out logic in ``InboxFanOutService`` whenever a
    relevant issue event occurs.  Each user has their own copy so that
    ``is_read`` state is independent.
    """

    __tablename__ = "inbox_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    timeline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issue_timeline.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[InboxEventType] = mapped_column(String(32), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    # ── Composite index to speed up unread-count and per-user inbox queries ───
    __table_args__ = (
        Index("ix_inbox_items_user_is_read", "user_id", "is_read"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user = relationship("User", back_populates="inbox_items")
    issue = relationship("Issue", back_populates="inbox_items")
    timeline_event = relationship("IssueTimeline", back_populates="inbox_items")

    def __repr__(self) -> str:
        return f"<InboxItem user={self.user_id} type={self.event_type} read={self.is_read}>"
