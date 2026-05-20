"""IssueReproductionStep ORM model — ordered steps to reproduce an issue."""

import uuid

from sqlalchemy import ForeignKey, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IssueReproductionStep(Base):
    """An individual step in a numbered reproduction guide.

    Steps are ordered by ``step_order`` and each carries expected vs. actual
    results to make QA verification straightforward.
    """

    __tablename__ = "issue_reproduction_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(
        SmallInteger, nullable=False,
        doc="1-based display order of this step."
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False,
        doc="What the tester should do in this step."
    )
    expected_result: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="What should happen after performing the step."
    )
    actual_result: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="What actually happened — filled in when filing the bug."
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    issue = relationship("Issue", back_populates="reproduction_steps")

    def __repr__(self) -> str:
        return f"<IssueReproductionStep issue={self.issue_id} step={self.step_order}>"
