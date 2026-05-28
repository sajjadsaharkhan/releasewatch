"""IssueCycle ORM model — per-iteration timing metrics for an issue.

Each regression starts a new cycle so analytics can distinguish
'time to fix in pass 2' from 'time to fix in pass 1'.
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IssueCycle(Base):
    """One row per workflow iteration of an issue.

    Cycle 1: initial filing → triage → fix → verify.
    Cycle N (N > 1): triggered by regression N-1.

    time_to_triage_h = triaged_at - cycle_start_at
    time_to_fix_h    = fixed_at   - (triaged_at or cycle_start_at)
    time_to_verify_h = verified_at - fixed_at
    """

    __tablename__ = "issue_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    cycle_number: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1,
        doc="1-based: 1 = initial pass, 2 = after first regression, etc."
    )
    regression_history_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("regression_history.id", ondelete="SET NULL"),
        nullable=True,
        doc="Regression event that started this cycle. NULL for cycle 1."
    )
    cycle_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="filed_at for cycle 1; regression detected_at for later cycles."
    )
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fixed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    time_to_triage_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_to_fix_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_to_verify_h: Mapped[float | None] = mapped_column(Float, nullable=True)

    issue = relationship("Issue", back_populates="cycles")
    regression_history = relationship("RegressionHistory", foreign_keys=[regression_history_id])

    def __repr__(self) -> str:
        return f"<IssueCycle issue={self.issue_id} cycle={self.cycle_number}>"
