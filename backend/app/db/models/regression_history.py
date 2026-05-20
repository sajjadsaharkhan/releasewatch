"""RegressionHistory ORM model — tracks each time an issue regresses."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, SmallInteger
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RegressionHistory(Base):
    """Records a single regression event for an issue within a release.

    When an issue that was marked ``fixed`` resurfaces in a later release it is
    promoted to ``regression`` status and a new ``RegressionHistory`` row is
    inserted.  The ``previous_fix_timeline_id`` links back to the fix comment
    so engineers can see who signed off on the original fix.
    """

    __tablename__ = "regression_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    regression_number: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1,
        doc="Incrementing count of how many times this issue has regressed."
    )
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    detected_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    previous_fix_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        doc="The developer who submitted the fix that later regressed."
    )
    previous_fix_timeline_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issue_timeline.id", ondelete="SET NULL"),
        nullable=True,
        doc="Timeline event (type=fixed) for the fix that later regressed."
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    issue = relationship("Issue", back_populates="regression_histories")
    release = relationship("Release", back_populates="regression_histories")
    detected_by = relationship("User", foreign_keys=[detected_by_id])
    previous_fix_by = relationship("User", foreign_keys=[previous_fix_by_id])
    previous_fix_timeline = relationship("IssueTimeline", foreign_keys=[previous_fix_timeline_id])

    def __repr__(self) -> str:
        return (
            f"<RegressionHistory issue={self.issue_id} "
            f"release={self.release_id} n={self.regression_number}>"
        )
