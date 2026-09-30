"""Issue ORM model — the core entity in Releasewatch."""

import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Computed, Date, DateTime, Float, ForeignKey, ForeignKeyConstraint, func, Integer, JSON, SmallInteger, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IssueType(str, enum.Enum):
    """Bug or task (slice 03). Fixed once the item is created (BR-07)."""

    bug = "bug"
    task = "task"


#: Display key prefix per type, e.g. "BUG-123" / "TASK-124".
ISSUE_TYPE_KEY_PREFIX = {IssueType.bug: "BUG", IssueType.task: "TASK"}


def issue_type_value(value: "IssueType | str | None") -> str:
    """Normalize an item type (enum member, string, or column value) to its string."""
    raw = getattr(value, "value", value)
    return raw or IssueType.bug.value


def issue_key(item_type: "IssueType | str | None", issue_number: int) -> str:
    """The display key, e.g. ``BUG-123`` / ``TASK-124`` — single source for every
    place that builds one (IssueResponse, CSV export, search, reports)."""
    prefix = ISSUE_TYPE_KEY_PREFIX.get(IssueType(issue_type_value(item_type)))
    return f"{prefix}-{issue_number}"


class Priority(str, enum.Enum):
    """The shared importance scale for bugs and tasks (BR-09, 03a).

    Null on a New or Needs info bug nobody has rated; required when a bug
    is accepted; a task starts at ``medium`` (BR-16).
    """

    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


#: Default priority for a new task (BR-16).
TASK_DEFAULT_PRIORITY = Priority.medium

#: Sort rank per priority, highest first (FR-37). Unrated sorts after every rank.
PRIORITY_RANK = {p: rank for rank, p in enumerate(Priority, start=1)}


class IssueStatus(str, enum.Enum):
    """Workflow state of an issue through its lifecycle.

    Shared by bugs and (from slice 03) tasks. See ``app/workflow.py`` for the
    allowed-transition rules — this enum only names the states.
    """

    new = "new"
    needs_info = "needs_info"
    todo = "todo"
    #: Delivered work sent back with a reason (09a, ADR 0004). Entered only by
    #: Reject or a merge into a Done item — never by ``/transition``.
    rejected = "rejected"
    in_progress = "in_progress"
    #: The developer has delivered; the work waits for QA to pick it up (09a).
    to_review = "to_review"
    in_review = "in_review"
    done = "done"
    blocked = "blocked"
    cancelled = "cancelled"


#: Statuses shown on a board (bugs and, from slice 03, tasks).
BOARD_STATUSES = (
    IssueStatus.todo,
    IssueStatus.rejected,
    IssueStatus.in_progress,
    IssueStatus.to_review,
    IssueStatus.in_review,
    IssueStatus.done,
    IssueStatus.blocked,
)

#: Bug-only pre-board statuses (BR-10) — kept off boards so untriaged work
#: never looks committed.
TRIAGE_STATUSES = (IssueStatus.new, IssueStatus.needs_info)

#: Statuses a backlog member can hold (BR-04): a board status that isn't Done.
#: New/Needs info are triage, not backlog; Cancelled is never on a board.
#: Rejected isn't either — it means nothing without a cycle, and the backlog
#: has none (09a): a rejected item entering the backlog becomes To do.
BACKLOG_STATUSES = tuple(
    s for s in BOARD_STATUSES if s not in (IssueStatus.done, IssueStatus.rejected)
)

#: Still needs work — neither Done nor Cancelled (triage included), as in the frontend.
OPEN_STATUSES = tuple(
    s for s in IssueStatus if s not in (IssueStatus.done, IssueStatus.cancelled)
)

#: Phase 1's "fixed": the developer has delivered the work (09a).
FIXED_STATUSES = (IssueStatus.to_review, IssueStatus.in_review, IssueStatus.done)

#: Where Reject is allowed from (09a): delivered or finished work.
REJECTABLE_STATUSES = FIXED_STATUSES

#: Delivery statuses — the first move into one stamps ``submitted_at`` (CY-05, 09a).
REVIEW_STATUSES = (IssueStatus.to_review, IssueStatus.in_review)

#: Statuses nothing leaves on its own — ``done`` is the one exception, via
#: the regression action (and, from slice 06, the merge regression).
TERMINAL_STATUSES = (IssueStatus.cancelled,)


class IssueCancelReason(str, enum.Enum):
    """Why an item was cancelled without being fixed/finished (BR-13).

    ``no_longer_needed`` is task-only; every other value is bug-only (03).
    """

    user_error = "user_error"
    expected_behavior = "expected_behavior"
    cannot_reproduce = "cannot_reproduce"
    duplicate = "duplicate"
    wont_fix = "wont_fix"
    no_longer_needed = "no_longer_needed"


class IssueSource(str, enum.Enum):
    """Who filed the item (slice 05). Support sees only ``support`` items (BR-30)."""

    internal = "internal"
    support = "support"


#: Human-readable cancel reasons — the Support ``support_cancelled`` message (§13).
CANCEL_REASON_LABELS = {
    IssueCancelReason.user_error: "User error",
    IssueCancelReason.expected_behavior: "Expected behavior",
    IssueCancelReason.cannot_reproduce: "Cannot reproduce",
    IssueCancelReason.duplicate: "Duplicate",
    IssueCancelReason.wont_fix: "Won't fix",
    IssueCancelReason.no_longer_needed: "No longer needed",
}

#: The reasons the Reject triage outcome accepts (FR-18, slice 06).
REJECT_REASONS = (
    IssueCancelReason.user_error,
    IssueCancelReason.expected_behavior,
    IssueCancelReason.cannot_reproduce,
)

#: Cancel reasons valid for a bug (BR-13) — excludes the task-only reason.
BUG_CANCEL_REASONS = tuple(r for r in IssueCancelReason if r != IssueCancelReason.no_longer_needed)

#: Cancel reasons valid for a task — only ever "no longer needed".
TASK_CANCEL_REASONS = (IssueCancelReason.no_longer_needed,)


class Issue(Base):
    """A bug, regression, or enhancement filed against a release.

    Issues carry rich environment metadata to aid reproduction and are linked
    to timeline events, attachments, and optionally a parent issue (duplicate).
    """

    __tablename__ = "issues"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "backlog_category_id"],
            ["backlog_categories.project_id", "backlog_categories.id"],
            name="fk_issues_backlog_category_same_project",
            onupdate="CASCADE",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_number: Mapped[int] = mapped_column(
        Integer, nullable=False,
        server_default=text("nextval('issue_number_seq')"),
        doc="Global sequential number assigned by DB sequence, starts at 10."
    )
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    release_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("releases.id", ondelete="SET NULL"), nullable=True, index=True,
        doc="The item's container — its project's Stream or one of its Releases; null is the backlog (08a)."
    )
    type: Mapped[IssueType] = mapped_column(
        String(16), nullable=False, default=IssueType.bug,
        doc="bug | task. Fixed at creation (BR-07)."
    )
    source: Mapped[IssueSource] = mapped_column(
        String(16), nullable=False, default=IssueSource.internal, index=True,
        doc="internal | support. Support reports come in through /support/reports (slice 05)."
    )
    recurrence_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        doc="How many times this problem has been reported. Incremented from 06/07."
    )
    backlog_category_id: Mapped[int] = mapped_column(
        Integer, nullable=False, index=True,
        doc="The item's category in its own project (never null — Default when none is "
            "chosen). Composite FK with project_id, so it can't point at another project's.",
    )
    backlog_rank: Mapped[float | None] = mapped_column(
        Float(precision=53), nullable=True,
        doc="Position in the project's backlog (midpoint ranking). Kept on leaving it."
    )
    is_tech_debt: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="Technical-debt flag — tasks only (BR-36). Hidden from the backlog by default."
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[Priority | None] = mapped_column(
        String(16), nullable=True, default=None,
        doc="Shared by bugs and tasks. Null on New/Needs info bugs nobody has rated yet (BR-16)."
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[IssueStatus] = mapped_column(
        String(32), nullable=False, default=IssueStatus.new
    )
    cancel_reason: Mapped[IssueCancelReason | None] = mapped_column(
        String(32), nullable=True,
        doc="Set when status is cancelled (BR-13); one of IssueCancelReason."
    )
    blocked_from_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        doc="Status to return to on unblock. Set on entering blocked, cleared on leaving it."
    )
    review_requested_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        doc="Who moved the item to in_review — used by the self_verification rule (AC-27)."
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

    # The current cycle (08a Part 2) — null exactly when release_id is null.
    # Written only by CycleService.
    current_cycle_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "issue_cycles.id", ondelete="SET NULL", use_alter=True,
            name="fk_issues_current_cycle_id",
        ),
        nullable=True,
    )

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
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="First time the item entered in_progress."
    )
    fixed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Set when done is reached from in_review (a verify pass). Non-null == \"Verified\"."
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Set when the item reaches done."
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    deleted_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, default=None
    )

    # Full-text search column — generated by the DB, never written by the app
    search_tsv = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title,'')), 'A') || "
            "setweight(to_tsvector('english', coalesce(description,'')), 'B')",
            persisted=True,
        ),
        nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    project = relationship("Project", back_populates="issues")
    backlog_category = relationship(
        "BacklogCategory",
        primaryjoin="Issue.backlog_category_id == BacklogCategory.id",
        foreign_keys="Issue.backlog_category_id",
        viewonly=True,
        # selectin, not joined: several paths lock issues with FOR UPDATE, which
        # Postgres refuses on the nullable side of an outer join.
        lazy="selectin",
    )
    release = relationship("Release", back_populates="issues")
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reported_issues")
    assignee = relationship("User", foreign_keys=[assignee_id], back_populates="assigned_issues")
    review_requested_by = relationship("User", foreign_keys=[review_requested_by_id])
    deleted_by = relationship("User", foreign_keys=[deleted_by_id])
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
    #: Always loaded (selectin) so Policy's snapshot of an issue can tell
    #: whether a Support viewer is subscribed (BR-30, slice 06).
    subscriptions = relationship("IssueSubscriber", lazy="selectin", viewonly=True)
    embeddings = relationship(
        "IssueEmbedding", back_populates="issue", cascade="all, delete-orphan",
    )
    cycles = relationship(
        "IssueCycle", back_populates="issue", cascade="all, delete-orphan",
        order_by="IssueCycle.cycle_number", foreign_keys="IssueCycle.issue_id",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Issue #{self.issue_number} status={self.status} priority={self.priority}>"
