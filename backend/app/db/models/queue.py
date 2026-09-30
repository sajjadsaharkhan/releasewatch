"""Personal queue ORM models (slice 10, FR-33–FR-41).

``QueueEntry`` — one per queued item (``issue_id`` is unique: an item is in at
most one queue, its assignee's). Written only by ``QueueService``.

``QueueHistory`` — the owner's queue history: every human reorder, pin and
unpin (BR-44). Append-only; automatic insertions and removals aren't recorded.
Separate from item timelines (FR-41).
"""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class QueueEntry(Base):
    __tablename__ = "queue_entries"
    __table_args__ = (Index("ix_queue_entries_user_active", "user_id", "left_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, unique=True,
    )
    position: Mapped[float] = mapped_column(
        Float(precision=53), nullable=False,
        doc="Order within the entry's own group (pinned or rest) — never across groups.",
    )
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pinned_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    pin_locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="Set by a CTO or Admin pinning someone else's queue — the owner can't unpin (BR-41).",
    )
    pinned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Set while the item is Done: a dormant entry keeps its rest-group position "
            "so a Reject brings it back there (FR-64). Hidden from every queue read.",
    )

    issue = relationship("Issue")
    pinned_by = relationship("User", foreign_keys=[pinned_by_id])


class QueueAction(str, enum.Enum):
    reorder = "reorder"
    pin = "pin"
    unpin = "unpin"


class QueueHistory(Base):
    __tablename__ = "queue_history"
    __table_args__ = (Index("ix_queue_history_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    #: The queue's owner.
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    action: Mapped[QueueAction] = mapped_column(String(16), nullable=False)
    issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="SET NULL"), nullable=True,
    )
    #: 1-based places in the full queue (pins first) before and after the change.
    old_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    actor = relationship("User", foreign_keys=[actor_id])
    issue = relationship("Issue")
