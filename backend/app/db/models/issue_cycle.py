"""IssueCycle ORM model — one pass of work on an item (docs/phase-2/cycle-model.md).

A cycle belongs to one item and one container. It exists only while the item
has a container: cycle 1 starts when the item is placed (``planned``); every
later cycle starts because the work came back, and ``start_reason`` says where
it was caught (``review``, ``release_qa``, ``production``). Moving the item to
the backlog deletes its cycles.

``CycleService`` (``app/services/cycle_service.py``) is the only writer of this
table and of ``issues.current_cycle_id``.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKey, Integer, SmallInteger, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CycleStartReason(str, enum.Enum):
    """Why a cycle started (cycle-model §3). Stored when the cycle starts, never recomputed."""

    #: The item was placed in a container. Always cycle 1.
    planned = "planned"
    #: Item-level QA rejected the delivered work (In review → To do).
    review = "review"
    #: Release-level QA found a problem with a Done item in a Release that hasn't shipped.
    release_qa = "release_qa"
    #: A problem was found on production (an escape).
    production = "production"


#: The cycles Phase 1 recorded as regressions — what Phase 1 reports keep counting
#: (bugs only, in ``kind = release`` containers; 08a Part 2).
PHASE1_REGRESSION_REASONS = (CycleStartReason.review, CycleStartReason.release_qa)


class IssueCycle(Base):
    """One row per pass of work on an item."""

    __tablename__ = "issue_cycles"
    __table_args__ = (
        UniqueConstraint("issue_id", "cycle_number", name="uq_issue_cycles_issue_id_cycle_number"),
        CheckConstraint(
            "start_reason IN ('planned', 'review', 'release_qa', 'production')",
            name="ck_issue_cycles_start_reason",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cycle_number: Mapped[int] = mapped_column(
        SmallInteger, nullable=False,
        doc="1-based. \"Returned N\" is cycle_number − 1.",
    )
    release_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("releases.id", ondelete="CASCADE"), nullable=False, index=True,
        doc="The cycle's container (CY-01). Follows the item until it is Done.",
    )
    start_reason: Mapped[CycleStartReason] = mapped_column(String(16), nullable=False)
    start_comment_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issue_timeline.id", ondelete="SET NULL"), nullable=True,
        doc="The public comment carrying the reason; null for planned.",
    )
    start_merged_issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="SET NULL"), nullable=True,
        doc="The report whose merge started this cycle.",
    )
    start_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        doc="Who started it — audit and timeline only, never attribution (CY-06).",
    )
    assignee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
        doc="Tracks reassignment during the cycle. Not attribution — see delivered_by_id.",
    )
    delivered_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True,
        doc="The assignee when the work went to In review (CY-05). Never the actor; "
            "empty when the item had no assignee. Written once.",
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    picked_up_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="First move to In progress in this cycle."
    )
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="First move to In review in this cycle."
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="The next cycle started, or the item was cancelled.",
    )

    issue = relationship("Issue", back_populates="cycles", foreign_keys=[issue_id])
    release = relationship("Release", foreign_keys=[release_id])
    assignee = relationship("User", foreign_keys=[assignee_id])
    delivered_by = relationship("User", foreign_keys=[delivered_by_id])
    start_by = relationship("User", foreign_keys=[start_by_id])

    @property
    def is_return(self) -> bool:
        reason = getattr(self.start_reason, "value", self.start_reason)
        return reason != CycleStartReason.planned.value

    def __repr__(self) -> str:
        return (
            f"<IssueCycle issue={self.issue_id} cycle={self.cycle_number} "
            f"reason={self.start_reason}>"
        )
