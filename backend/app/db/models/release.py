"""Release ORM model."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReleaseStatus(str, enum.Enum):
    """Lifecycle status of a release cycle."""

    active = "active"
    released = "released"
    blocked = "blocked"
    archived = "archived"


class GoNogoStatus(str, enum.Enum):
    """Go/No-go gate decision for releasing to production."""

    pending = "pending"
    approved = "approved"
    blocked = "blocked"


class Release(Base):
    """A versioned release within a project.

    Tracks the QA cycle from ``draft`` through ``active`` to ``released``.
    The go/no-go decision gates production deployment.
    """

    __tablename__ = "releases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="Semantic version string, e.g. '2.4.1'"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Release description / notes"
    )
    status: Mapped[ReleaseStatus] = mapped_column(
        String(32), nullable=False, default=ReleaseStatus.active
    )
    target_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Target release date"
    )
    staging_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Go/No-go gate
    go_nogo_status: Mapped[GoNogoStatus] = mapped_column(
        String(32), nullable=False, default=GoNogoStatus.pending
    )
    go_nogo_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    go_nogo_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    go_nogo_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Triage
    triage_lead_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Audit
    created_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", onupdate=datetime.utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    project = relationship("Project", back_populates="releases")
    creator = relationship("User", foreign_keys=[created_by_id])
    go_nogo_user = relationship("User", foreign_keys=[go_nogo_by_id])
    triage_lead = relationship("User", foreign_keys=[triage_lead_id])
    issues = relationship("Issue", back_populates="release")
    regression_histories = relationship("RegressionHistory", back_populates="release")

    def __repr__(self) -> str:
        return f"<Release id={self.id} version={self.version!r} status={self.status}>"
