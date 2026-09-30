"""Release ORM model — every container an item can be placed in (PRD v3 §8.1).

A project has exactly one **Stream** (``kind = stream``: always open, each
item ships on its own when Done) and any number of **Releases**
(``kind = release``: their items ship together). An issue's ``release_id``
points at either; ``null`` is the backlog. See docs/phase-2/cycle-model.md.
"""

import enum
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, String, Text, event, text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReleaseKind(str, enum.Enum):
    """What a container is (08a)."""

    stream = "stream"
    release = "release"


class ReleaseStatus(str, enum.Enum):
    """Lifecycle of a Release (PRD v3 §8.7). The Stream has no status.

    A blocked release is a release in QA with a no-go decision — not a status.
    """

    planning = "planning"
    development = "development"
    qa = "qa"
    released = "released"
    cancelled = "cancelled"


#: A Release still in the works (dashboards' "active releases").
OPEN_RELEASE_STATUSES = (ReleaseStatus.planning, ReleaseStatus.development, ReleaseStatus.qa)

#: Release statuses that take no new items (``release_closed``).
CLOSED_RELEASE_STATUSES = (ReleaseStatus.released, ReleaseStatus.cancelled)

#: The Stream's fixed label — it can't be renamed (FR-46).
STREAM_NAME = "Stream"


class GoNogoStatus(str, enum.Enum):
    """Go/No-go gate decision for releasing to production."""

    pending = "pending"
    approved = "approved"
    blocked = "blocked"


class Release(Base):
    """A container within a project: its Stream or one of its Releases."""

    __tablename__ = "releases"
    __table_args__ = (
        # One Stream per project (BR-51).
        Index(
            "uq_releases_one_stream_per_project",
            "project_id",
            unique=True,
            postgresql_where=text("kind = 'stream'"),
        ),
        # A Release always has a lifecycle status; the Stream never does.
        CheckConstraint(
            "(kind = 'stream' AND status IS NULL) OR (kind = 'release' AND status IS NOT NULL)",
            name="ck_releases_status_by_kind",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[ReleaseKind] = mapped_column(
        String(16), nullable=False, default=ReleaseKind.release, server_default="release",
        doc="stream | release. The Stream is created with its project and never changes.",
    )
    version: Mapped[str] = mapped_column(
        String(64), nullable=False, doc="Semantic version string, e.g. '2.4.1'"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, doc="Release description / notes"
    )
    status: Mapped[ReleaseStatus | None] = mapped_column(
        String(32), nullable=True, default=None,
        doc="Lifecycle status of a Release; null for the Stream.",
    )
    code_freeze_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, doc="When QA starts (optional)."
    )
    target_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Target ship date"
    )
    released_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="When the release shipped."
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

    #: When the CTOs were told the release passed its target ship date (slice 09);
    #: cleared whenever ``target_date`` changes, so a later date notifies again.
    overdue_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    @property
    def is_stream(self) -> bool:
        return getattr(self.kind, "value", self.kind) == ReleaseKind.stream.value

    @property
    def is_shipped(self) -> bool:
        """True once a Release has shipped. The Stream never "ships" as a whole —
        each of its items is shipped when Done (cycle-model §2)."""
        return getattr(self.status, "value", self.status) == ReleaseStatus.released.value

    @property
    def is_closed(self) -> bool:
        """A Release that takes no new items: released or cancelled."""
        return getattr(self.status, "value", self.status) in {
            s.value for s in CLOSED_RELEASE_STATUSES
        }

    # ── Relationships ─────────────────────────────────────────────────────────
    project = relationship("Project", back_populates="releases")
    creator = relationship("User", foreign_keys=[created_by_id])
    go_nogo_user = relationship("User", foreign_keys=[go_nogo_by_id])
    issues = relationship("Issue", back_populates="release")
    events = relationship(
        "ReleaseEvent", cascade="all, delete-orphan", passive_deletes=True,
        order_by="ReleaseEvent.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<Release id={self.id} kind={self.kind} version={self.version!r} "
            f"status={self.status}>"
        )


def _default_release_status(mapper, connection, release) -> None:
    """A Release inserted without a status starts in Planning; the Stream has none."""
    kind = getattr(release.kind, "value", release.kind) or ReleaseKind.release.value
    if kind == ReleaseKind.stream.value:
        release.status = None
    elif release.status is None:
        release.status = ReleaseStatus.planning


def _create_stream(mapper, connection, project) -> None:
    """Every project gets its Stream the moment it exists, in the same transaction
    (BR-51, AC-55) — API, seeds and scripts alike."""
    connection.execute(
        Release.__table__.insert().values(
            project_id=project.id,
            kind=ReleaseKind.stream.value,
            version=STREAM_NAME,
            status=None,
            go_nogo_status=GoNogoStatus.pending.value,
        )
    )


def register_stream_hooks(project_cls) -> None:
    event.listen(Release, "before_insert", _default_release_status)
    event.listen(project_cls, "after_insert", _create_stream)
