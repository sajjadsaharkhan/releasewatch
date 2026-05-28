"""SQLAlchemy async declarative base and shared mixins."""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Project-wide declarative base.

    All ORM models must inherit from this class so that Alembic can discover
    their metadata via ``Base.metadata``.
    """


class TimestampMixin:
    """Mixin that adds ``created_at``, ``updated_at``, and ``deleted_at`` columns.

    ``created_at`` and ``updated_at`` are managed by the database server via
    ``server_default`` and ``onupdate`` triggers so they are always consistent
    even when rows are modified outside SQLAlchemy.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="Timestamp when the row was first inserted.",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="Timestamp of the last UPDATE, kept current by SQLAlchemy's onupdate hook.",
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        doc="Soft-delete timestamp; NULL means the row is active.",
    )


