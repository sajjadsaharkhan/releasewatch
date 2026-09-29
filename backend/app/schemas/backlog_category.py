"""Backlog category schemas (2026-09-28 — categories per project)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.db.models.backlog_category import (
    CATEGORY_COLORS,
    CATEGORY_ICONS,
    MAX_CATEGORY_NAME_LENGTH,
)

CategoryName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_CATEGORY_NAME_LENGTH),
]


def _check_icon(value: str | None) -> str | None:
    if value is not None and value not in CATEGORY_ICONS:
        raise ValueError("Pick one of the category icons.")
    return value


def _check_color(value: str | None) -> str | None:
    if value is not None and value not in CATEGORY_COLORS:
        raise ValueError("Pick one of the category colours.")
    return value


class BacklogCategoryOut(BaseModel):
    """A category as items and pickers show it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    icon: str
    color: str
    position: int = 0
    is_default: bool = False


class BacklogCategoryWithCount(BacklogCategoryOut):
    #: Items (not deleted) using it — the delete dialog's "N items move to Default".
    item_count: int = 0


class BacklogCategoryList(BaseModel):
    """GET /projects/{id}/backlog-categories — Default first, then by position."""

    project_id: int
    categories: list[BacklogCategoryWithCount]
    #: ``manage_backlog_categories`` for the caller (CTO/Admin).
    can_manage: bool = False


class BacklogCategoryCreate(BaseModel):
    name: CategoryName
    icon: str
    color: str

    _icon = field_validator("icon")(_check_icon)
    _color = field_validator("color")(_check_color)


class BacklogCategoryUpdate(BaseModel):
    name: CategoryName | None = None
    icon: str | None = None
    color: str | None = None

    _icon = field_validator("icon")(_check_icon)
    _color = field_validator("color")(_check_color)


class BacklogCategoryOrder(BaseModel):
    """Every non-Default category id, in the new order. Default always stays first."""

    ids: list[int] = Field(default_factory=list)


class BacklogCategoryDeleted(BaseModel):
    #: Items moved to Default.
    moved_count: int
    default_category: BacklogCategoryOut
