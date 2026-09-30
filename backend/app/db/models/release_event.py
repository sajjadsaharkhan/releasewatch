"""ReleaseEvent ORM model — the release page's Activity tab (slice 09, FR-51).

Separate from item timelines: lifecycle changes, date changes, items added or
removed, go/no-go decisions, the ship, and other edits. Written only by
``ReleaseService``.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ReleaseEventType(str, enum.Enum):
    #: meta ``{from, to}``
    status_changed = "status_changed"
    #: meta ``{changes: {field: {from, to}}}`` for code_freeze_date / target_date
    dates_changed = "dates_changed"
    #: meta ``{issue_id, issue_number, key, title}``
    item_added = "item_added"
    #: meta ``{issue_id, issue_number, key, title, reason?}`` — reason ``ship`` / ``cancel``
    item_removed = "item_removed"
    #: meta ``{decision, note}``
    go_nogo = "go_nogo"
    #: meta ``{moved: int, not_done: {status: count}}``
    shipped = "shipped"
    #: meta ``{changes: {field: {from, to}}}`` for version / description / staging_url
    edited = "edited"


class ReleaseEvent(Base):
    __tablename__ = "release_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    release_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("releases.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[ReleaseEventType] = mapped_column(String(32), nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    actor = relationship("User", foreign_keys=[actor_id])
