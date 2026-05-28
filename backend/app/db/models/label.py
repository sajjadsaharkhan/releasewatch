"""Label ORM model — predefined categories for tagging issues."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Label(Base):
    """A predefined label that can be applied to issues.

    Labels provide a way to categorize and filter issues by component,
    severity tier, or any other taxonomy the team defines.
    """

    __tablename__ = "labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True,
        doc="Human-readable label name, e.g. 'auth', 'payments', 'UI/UX'."
    )
    color: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#6366f1",
        doc="Hex color code for UI display, e.g. '#ef4444'."
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    def __repr__(self) -> str:
        return f"<Label id={self.id} name={self.name!r}>"
