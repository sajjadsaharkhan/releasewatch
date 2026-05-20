"""Issue ORM model — the core entity in Releasewatch."""

import uuid
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IssueSeverity(str, enum.Enum):
    """How badly the issue impacts end-users or release quality."""

    blocker = "blocker"
    critical = "critical"
    major = "major"
    minor = "minor"
    enhancement = "enhancement"


class IssueStatus(str, enum.Enum):
    """Workflow state of an issue through its lifecycle."""

    new = "new"
    triaged = "triaged"
    in_progress = "in_progress"
    fixed = "fixed"
    verified = "verified"
    closed = "closed"
    regression = "regression"


class Issue(Base):
    """A bug, regression, or enhancement filed against a release.

    Issues carry rich environment metadata to aid reproduction and are linked
    to timeline events, attachments, and optionally a parent issue (duplicate).
    """

    __tablename__ = "issues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issue_number: Mapped[int] = mapped_column(
        Integer, nullable=False,
        doc="Human-friendly sequential number scoped to the project."
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("releases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[IssueSeverity] = mapped_column(
        String(32), nullable=False, default=IssueSeverity.minor
    )
    status: Mapped[IssueStatus] = mapped_column(
        String(32), nullable=False, default=IssueStatus.new
    )

    # People
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Taxonomy
    labels: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    is_release_blocker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_regression: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    regression_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    # Duplicate linking
    parent_issue_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="SET NULL"), nullable=True
    )

    # Environment / repro context
    environment_browser: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment_os: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment_build_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    environment_staging_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    curl_command: Mapped[str | None] = mapped_column(Text, nullable=True)

    # SLA / lead-time metrics (computed and stored for fast reporting)
    time_to_triage_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_to_fix_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_to_verify_h: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Lifecycle timestamps
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fixed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()", onupdate=datetime.utcnow
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    project = relationship("Project", back_populates="issues")
    release = relationship("Release", back_populates="issues")
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reported_issues")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_issues")
    parent = relationship("Issue", remote_side="Issue.id", foreign_keys=[parent_issue_id])
    duplicates = relationship("Issue", foreign_keys="Issue.parent_issue_id")
    reproduction_steps = relationship(
        "IssueReproductionStep", back_populates="issue", cascade="all, delete-orphan",
        order_by="IssueReproductionStep.step_order",
    )
    timeline = relationship(
        "IssueTimeline", back_populates="issue", cascade="all, delete-orphan",
        order_by="IssueTimeline.created_at",
    )
    attachments = relationship(
        "IssueAttachment", back_populates="issue", cascade="all, delete-orphan"
    )
    inbox_items = relationship("InboxItem", back_populates="issue")
    regression_histories = relationship("RegressionHistory", back_populates="issue")

    def __repr__(self) -> str:
        return f"<Issue #{self.issue_number} status={self.status} severity={self.severity}>"
