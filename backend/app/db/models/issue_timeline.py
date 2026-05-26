"""IssueTimeline ORM model — append-only audit trail for every issue event."""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimelineEventType(str, enum.Enum):
    """Every discrete event that can appear on an issue's timeline."""

    filed = "filed"
    status_changed = "status_changed"
    severity_changed = "severity_changed"
    assigned = "assigned"
    label_added = "label_added"
    label_removed = "label_removed"
    blocker_flagged = "blocker_flagged"
    blocker_cleared = "blocker_cleared"
    comment = "comment"
    fixed = "fixed"
    verified = "verified"
    regression = "regression"
    duplicate_linked = "duplicate_linked"
    reopened = "reopened"
    title_changed = "title_changed"
    description_changed = "description_changed"
    steps_changed = "steps_changed"
    release_changed = "release_changed"
    project_changed = "project_changed"
    environment_changed = "environment_changed"


class IssueTimeline(Base):
    """A single entry on the issue's immutable event log.

    System events (status changes, assignments, …) are generated automatically
    by service methods.  ``comment`` events are authored by users and may be
    edited.  ``is_internal`` marks notes only visible to the QA team.
    """

    __tablename__ = "issue_timeline"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[TimelineEventType] = mapped_column(String(32), nullable=False)
    body: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        doc="Human-readable note or comment body (Markdown supported)."
    )
    is_internal: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        doc="True → visible only to logged-in team members, not external stakeholders."
    )
    meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        doc="Structured diff payload, e.g. {from: 'new', to: 'triaged'} for status_changed."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(tz=timezone.utc)
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    issue = relationship("Issue", back_populates="timeline")
    actor = relationship("User", foreign_keys=[actor_id])
    inbox_items = relationship("InboxItem", back_populates="timeline_event")

    def __repr__(self) -> str:
        return f"<IssueTimeline issue={self.issue_id} type={self.event_type}>"
