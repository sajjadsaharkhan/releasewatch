"""User acknowledgements (TASK-575) — what a person has already seen once.

One row per ``(user, kind, key)``: ``note`` + a What's new note id
(``2026-10-24``) means that person has seen the note, so its modal never opens
for them again, on any device. The first sighting wins; seeing it again changes
nothing.
"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AcknowledgementKind(str, enum.Enum):
    #: A What's new note, keyed by its id.
    note = "note"


class UserAcknowledgement(Base):
    __tablename__ = "user_acknowledgements"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[AcknowledgementKind] = mapped_column(String(16), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
