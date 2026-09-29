"""BacklogCategory — a project's own backlog categories (slice 08 follow-up, 2026-09-28).

Every project has a fixed **Default** category (created with the project, never
renamed, recoloured, moved or deleted — always first) plus any categories CTO
and Admin add in Settings → Backlog categories. Every issue points at exactly
one category of its own project: ``issues.backlog_category_id`` is NOT NULL and
a composite foreign key ``(project_id, backlog_category_id)`` →
``backlog_categories (project_id, id)`` makes a cross-project category
impossible at the database level. Deleting a category first moves its items
to the project's Default (``BacklogCategoryService.delete``).

Icons and colours come from curated sets (``CATEGORY_ICONS``,
``CATEGORY_COLORS``) mirrored in ``frontend/src/lib/constants.js`` — free
colours break dark mode and collide with the priority/status hues.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

#: The fixed first category every project gets.
DEFAULT_CATEGORY_NAME = "Default"
DEFAULT_CATEGORY_ICON = "inbox"
DEFAULT_CATEGORY_COLOR = "zinc"

#: lucide icon names a category may use (kebab-case, as the frontend's <Icon> takes them).
CATEGORY_ICONS: tuple[str, ...] = (
    "inbox",
    "sparkles",
    "trending-up",
    "telescope",
    "rocket",
    "lightbulb",
    "wrench",
    "gauge",
    "shield-check",
    "lock",
    "palette",
    "layout-grid",
    "smartphone",
    "globe",
    "database",
    "server",
    "zap",
    "heart",
    "star",
    "flag",
    "target",
    "puzzle",
    "book-open",
    "users",
    "message-square",
    "bell",
    "bar-chart-3",
    "bug-off",
    "accessibility",
    "search",
)

#: Tailwind hues a category may use — each has a light/dark treatment in the frontend.
CATEGORY_COLORS: tuple[str, ...] = (
    "zinc",
    "slate",
    "stone",
    "emerald",
    "teal",
    "cyan",
    "sky",
    "indigo",
    "violet",
    "fuchsia",
    "pink",
    "lime",
)

#: Per-project limits (2026-09-28 decision).
MAX_CATEGORIES_PER_PROJECT = 20
MAX_CATEGORY_NAME_LENGTH = 40


class BacklogCategory(Base):
    __tablename__ = "backlog_categories"
    __table_args__ = (
        # Target of the issues composite FK — a category is only ever used in its project.
        UniqueConstraint("project_id", "id", name="uq_backlog_categories_project_id_id"),
        # One Default per project.
        Index(
            "uq_backlog_categories_one_default",
            "project_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
        # Names are unique per project, ignoring case.
        Index(
            "uq_backlog_categories_project_name",
            "project_id",
            func.lower(text("name")),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(MAX_CATEGORY_NAME_LENGTH), nullable=False)
    icon: Mapped[str] = mapped_column(String(40), nullable=False, default=DEFAULT_CATEGORY_ICON)
    color: Mapped[str] = mapped_column(String(16), nullable=False, default=DEFAULT_CATEGORY_COLOR)
    #: Order in pickers and the grouped backlog. Default is always 0.
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return (
            f"<BacklogCategory {self.name!r} project={self.project_id} default={self.is_default}>"
        )


def _create_default_category(mapper, connection, project) -> None:
    """Every project gets its Default the moment it exists — API, seeds and
    scripts alike — so no issue can ever lack a category to point at."""
    connection.execute(
        BacklogCategory.__table__.insert().values(
            project_id=project.id,
            name=DEFAULT_CATEGORY_NAME,
            icon=DEFAULT_CATEGORY_ICON,
            color=DEFAULT_CATEGORY_COLOR,
            position=0,
            is_default=True,
        )
    )


def _default_issue_category(mapper, connection, issue) -> None:
    """An issue inserted without a category points at its project's Default —
    the domain rule holds for every writer (seeds and scripts too), not only
    ``IssueService``."""
    if issue.backlog_category_id is not None:
        return
    table = BacklogCategory.__table__
    issue.backlog_category_id = connection.execute(
        select(table.c.id).where(table.c.project_id == issue.project_id, table.c.is_default)
    ).scalar_one()


def register_default_category_hook(project_cls, issue_cls) -> None:
    event.listen(project_cls, "after_insert", _create_default_category)
    event.listen(issue_cls, "before_insert", _default_issue_category)
