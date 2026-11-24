"""Return requests (slice 20, PRD v3.1 §8.10) — Support's "Problem is back".

A request is not a work item: it hangs off a Done item, is listed in the
project's triage queue while Pending, and is written on the item's timeline.
``ReturnRequestService`` is the only writer. One Pending request per item
(BR-69) — the partial unique index is the backstop for the service's lock.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReturnRequestStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    dismissed = "dismissed"


class ReturnRequest(Base):
    __tablename__ = "return_requests"
    __table_args__ = (
        Index(
            "uq_return_requests_one_pending", "issue_id", unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=ReturnRequestStatus.pending.value,
        server_default=ReturnRequestStatus.pending.value,
    )
    requested_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_comment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue_timeline.id", ondelete="SET NULL"), nullable=True
    )
    #: The first requester's comment — the reason a confirmed request rejects with.
    start_comment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue_timeline.id", ondelete="SET NULL"), nullable=True
    )
    #: Null for parity with other records; agents can't create one (BR-M04).
    via_mcp_token_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("mcp_tokens.id", ondelete="SET NULL"), nullable=True
    )

    entries = relationship(
        "ReturnRequestEntry", order_by="ReturnRequestEntry.id", lazy="selectin",
        cascade="all, delete-orphan",
    )
    requested_by = relationship("User", foreign_keys=[requested_by_id], lazy="selectin")
    decided_by = relationship("User", foreign_keys=[decided_by_id], lazy="selectin")


class ReturnRequestEntry(Base):
    """One press of Problem is back — the first included."""

    __tablename__ = "return_request_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("return_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    comment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue_timeline.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = relationship("User", lazy="selectin")
