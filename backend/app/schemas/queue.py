"""Personal queue and board schemas (slice 10)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from app.db.models.issue import ISSUE_TYPE_KEY_PREFIX, IssueStatus, IssueType, Priority
from app.schemas.issue import UserSummary


class CardProject(BaseModel):
    id: int
    slug: str
    name: str
    color: str


class CardContainer(BaseModel):
    #: ``stream`` | ``release``
    kind: str
    name: str
    #: The release's lifecycle status; ``None`` for the Stream.
    status: str | None = None


class CardLabel(BaseModel):
    name: str
    color: str


class WorkItemCard(BaseModel):
    """The slim item shared by the queue, the personal board, and item lists (FR-42, P3).

    Default fields are always shown; signal fields drive the compact markers,
    which appear only when they matter; hover fields fill the hover card.
    """

    # Default
    id: int
    issue_number: int
    type: IssueType
    title: str
    project: CardProject
    status: IssueStatus
    priority: Priority | None = None

    # Signals
    recurrence_count: int = 1
    due_date: date | None = None
    #: ``none`` | ``soon`` (due within 2 days) | ``overdue`` — computed server-side.
    due_state: Literal["none", "soon", "overdue"] = "none"
    is_tech_debt: bool = False
    is_release_blocker: bool = False
    pinned: bool = False
    pin_locked: bool = False
    #: The current cycle's number — the cycle badge shows from 2 (09a).
    cycle_number: int | None = None
    #: How many cycles the item has had in its placement (0 in the backlog).
    cycle_count: int = 0
    #: While Rejected: ``review`` | ``release_qa`` | ``production`` (09a).
    reject_reason: str | None = None
    #: The Reject comment, fetched lazily on hover (``GET /issues/{id}/timeline/{event_id}``).
    reject_comment_id: int | None = None

    # Hover
    container: CardContainer | None = None
    labels: list[CardLabel] = Field(default_factory=list)
    reporter: UserSummary | None = None
    assignee: UserSummary | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @computed_field  # type: ignore[misc]
    @property
    def key(self) -> str:
        return f"{ISSUE_TYPE_KEY_PREFIX[self.type]}-{self.issue_number}"


class QueueEntryOut(BaseModel):
    issue: WorkItemCard
    pinned: bool
    pin_locked: bool
    pinned_by: UserSummary | None = None


class QueueGroups(BaseModel):
    pinned: list[QueueEntryOut] = Field(default_factory=list)
    rest: list[QueueEntryOut] = Field(default_factory=list)


class QueueResponse(BaseModel):
    owner: UserSummary
    groups: QueueGroups
    pin_limit: int
    pins_used: int
    can_reorder: bool
    can_pin: bool
    #: Why the controls are off, for the disabled-control tooltip.
    disabled_reason: str | None = None


class BoardColumnOut(BaseModel):
    status: str
    items: list[WorkItemCard]


class PersonalBoardResponse(BaseModel):
    owner: UserSummary
    columns: list[BoardColumnOut]
    #: The Done column's window — ``done_from``/``done_to`` when given, else the last 7 days.
    done_from: datetime
    done_to: datetime | None = None


class QueueMoveRequest(BaseModel):
    issue_id: int
    before_id: int | None = None
    after_id: int | None = None


class QueuePinRequest(BaseModel):
    issue_id: int


class QueueHistoryItem(BaseModel):
    id: int
    action: Literal["reorder", "pin", "unpin"]
    actor: UserSummary | None = None
    issue_id: int | None = None
    issue_key: str | None = None
    issue_title: str | None = None
    issue_type: str | None = None
    old_index: int | None = None
    new_index: int | None = None
    created_at: datetime


class HistoryActorCount(BaseModel):
    actor: UserSummary
    count: int


class QueueHistoryFacets(BaseModel):
    """Counts within the date range (and search), before the other filters —
    what each filter option would show."""

    total: int
    not_owner: int
    actions: dict[str, int]
    types: dict[str, int]
    actors: list[HistoryActorCount]


class QueueHistoryResponse(BaseModel):
    items: list[QueueHistoryItem]
    total: int
    page: int
    size: int
    facets: QueueHistoryFacets


class WorkloadCounts(BaseModel):
    #: Active queue entries — dormant (Done) entries never count.
    open: int
    pinned: int


class WorkloadRow(BaseModel):
    """One person on the Team overview's Workload view (slice 11, FR-43)."""

    user: UserSummary
    #: Their In progress items, in queue order.
    in_progress: list[WorkItemCard]
    #: The first three queue items that aren't already In progress.
    next: list[WorkItemCard]
    counts: WorkloadCounts
