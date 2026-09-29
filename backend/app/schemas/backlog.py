"""Backlog and Technical debt schemas (slice 08)."""

from pydantic import BaseModel, Field, model_validator

from app.schemas.backlog_category import BacklogCategoryOut
from app.schemas.issue import BlockedAction, IssueResponse


class BacklogGroup(BaseModel):
    """One group of the grouped backlog view (FR-25).

    One group per project category, in the project's order (Default first,
    empty ones included), then ``tech_debt`` — every debt task whatever its
    category, only while debt is shown. ``key`` is the category id as a
    string, or ``"tech_debt"``. ``item_ids`` are in rank order.
    """

    key: str
    category: BacklogCategoryOut | None = None
    count: int
    item_ids: list[int]


class BacklogResponse(BaseModel):
    """GET /projects/{id}/backlog."""

    project_id: int
    #: Every visible member, in rank order.
    items: list[IssueResponse]
    total: int
    #: Members not updated for over 6 months — the header's hygiene hint
    #: (display only). ``stale_item_ids`` lets the page mark those rows.
    stale_count: int
    stale_item_ids: list[int] = Field(default_factory=list)
    #: Debt tasks hidden because ``include_tech_debt`` is off (0 when it's on).
    hidden_tech_debt_count: int
    #: Present when ``group_by=category``.
    groups: list[BacklogGroup] | None = None
    #: Policy for the caller on this project — ``manage_backlog`` drives drag and bulk move.
    allowed_actions: list[str] = Field(default_factory=list)
    blocked_actions: list[BlockedAction] = Field(default_factory=list)


class BacklogOrderRequest(BaseModel):
    """PUT /projects/{id}/backlog/order — place ``issue_id`` after ``after_id``
    (the item above it) and/or before ``before_id`` (the item below it)."""

    issue_id: int
    before_id: int | None = None
    after_id: int | None = None

    @model_validator(mode="after")
    def _one_anchor(self) -> "BacklogOrderRequest":
        if self.before_id is None and self.after_id is None:
            raise ValueError("Give before_id, after_id, or both.")
        if self.issue_id in (self.before_id, self.after_id):
            raise ValueError("An item can't be placed next to itself.")
        return self


class BacklogOrderResponse(BaseModel):
    issue_id: int
    backlog_rank: float


class BacklogCategoryRequest(BaseModel):
    """POST /projects/{id}/backlog/category — give several items one category, all or nothing."""

    issue_ids: list[int] = Field(min_length=1, max_length=500)
    backlog_category_id: int


class BacklogCategoryResponse(BaseModel):
    #: Items whose category changed — items already in it are skipped.
    updated_ids: list[int]
    items: list[IssueResponse]


class TechDebtListResponse(BaseModel):
    """GET /tech-debt."""

    items: list[IssueResponse]
    total: int
