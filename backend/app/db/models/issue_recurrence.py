"""Issue recurrences (slice 07) — one row per Report recurrence action.

The count the UI shows is still ``issues.recurrence_count``; these rows exist
so reports (slice 11) can count recurrences over time. Merges aren't recorded
here — they're counted from ``duplicate`` cancellations.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class IssueRecurrence(Base):
    __tablename__ = "issue_recurrences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reported_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    timeline_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue_timeline.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
