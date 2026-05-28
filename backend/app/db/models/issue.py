"""Issue ORM model — the core entity in Releasewatch."""

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_number: Mapped[int] = mapped_column(
        Integer, nullable=False,
        server_default=text("nextval('issue_number_seq')"),
        doc="Global sequential number assigned by DB sequence, starts at 10."
    )
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("releases.id", ondelete="CASCADE"), nullable=False, index=True
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
    reporter_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assignee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Taxonomy
    labels: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    is_release_blocker: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_regression: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    regression_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    # Duplicate linking
    parent_issue_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("issues.id", ondelete="SET NULL"), nullable=True
    )

    # Environment / repro context
    environment_browser: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment_os: Mapped[str | None] = mapped_column(String(128), nullable=True)
    environment_build_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    environment_staging_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    curl_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    environment_name: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        doc="Named environment: production | staging | development | local | qa"
    )
    reproduction_steps: Mapped[list | None] = mapped_column(
        JSON, nullable=True, default=list,
        doc="JSON array of reproduction steps: [{step_order, description, expected_result, actual_result}]"
    )

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
    timeline = relationship(
        "IssueTimeline", back_populates="issue", cascade="all, delete-orphan",
        order_by="IssueTimeline.created_at",
    )
    attachments = relationship(
        "IssueAttachment", back_populates="issue", cascade="all, delete-orphan"
    )
    inbox_items = relationship("InboxItem", back_populates="issue")
    regression_histories = relationship("RegressionHistory", back_populates="issue")
    cycles = relationship(
        "IssueCycle", back_populates="issue", cascade="all, delete-orphan",
        order_by="IssueCycle.cycle_number",
    )

    def __repr__(self) -> str:
        return f"<Issue #{self.issue_number} status={self.status} severity={self.severity}>"
