"""CommentReaction ORM model — emoji reactions on timeline comments."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CommentReaction(Base):
    """A single user's emoji reaction to a ``comment`` timeline event.

    ``emoji_key`` holds a canonical key from ``app.core.reactions``
    (``+1``, ``heart``, …) rather than the glyph itself.  Reactions are mutually
    exclusive — the unique constraint is on ``(timeline_id, user_id)``, so each
    user holds at most one reaction per comment and picking a new emoji replaces
    the previous one in place.
    """

    __tablename__ = "comment_reactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timeline_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("issue_timeline.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    emoji_key: Mapped[str] = mapped_column(
        String(16), nullable=False,
        doc="Canonical reaction key; validated against ALLOWED_REACTIONS."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(tz=timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("timeline_id", "user_id", name="uq_comment_reaction_user"),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    timeline_event = relationship("IssueTimeline", back_populates="comment_reactions")
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<CommentReaction timeline={self.timeline_id} user={self.user_id} key={self.emoji_key}>"
