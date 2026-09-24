"""Issue subscribers (slice 06) — who hears an item's Support-audience events.

Support learns an item's fate through three notifications only — Needs info,
Cancelled, Done (§13) — and those go to the item's subscribers with role
``support``. The reporter is subscribed on create; reporters of duplicates
merged into the item (06) and of recurrences (07) join later. One row per
``(issue, user)``: the first reason wins.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SubscriptionReason(str, enum.Enum):
    reporter = "reporter"
    recurrence = "recurrence"
    duplicate = "duplicate"


class IssueSubscriber(Base):
    __tablename__ = "issue_subscribers"
    __table_args__ = (
        UniqueConstraint("issue_id", "user_id", name="uq_issue_subscribers_issue_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason: Mapped[SubscriptionReason] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
