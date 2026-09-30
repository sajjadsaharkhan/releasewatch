"""Queue ordering — the pure rules of a personal queue (slice 10, FR-36–FR-40).

Plain values in, plain values out, like ``app/workflow.py``: no database. The
service (``QueueService``) loads entries, asks this module where things go,
and writes the positions it returns.

A queue has two groups, always in this order: **pinned** (at most
``PIN_LIMIT``), then **rest**. ``position`` orders entries within their own
group only. A newly assigned item enters the rest group by the **default
rule** — directly above the first item that ranks lower (FR-39) — even when
the owner has ordered the rest by hand.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime

from app.db.models.issue import PRIORITY_RANK, Priority

#: A queue holds at most this many pins (FR-40, BR-40).
PIN_LIMIT = 4

#: Gap between consecutive positions after a renumber, and past either end.
POSITION_STEP = 1024.0
#: The narrowest half-gap a midpoint may leave; below it the group is renumbered.
MIN_GAP = 1e-6

#: Unrated items sort after every priority rank.
_UNRATED_RANK = len(PRIORITY_RANK) + 1


@dataclass(frozen=True)
class QueueItem:
    """What ordering needs to know about one queued item."""

    issue_id: int
    priority: str | None
    due_date: date | None
    recurrence_count: int
    created_at: datetime
    pinned: bool = False
    position: float = 0.0


class QueueRuleError(Exception):
    """A queue rule refused a change — the service turns it into a 409/404."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(detail)


def priority_rank(priority: "Priority | str | None") -> int:
    """1 (critical) … 4 (low); unrated last."""
    raw = getattr(priority, "value", priority)
    if raw is None:
        return _UNRATED_RANK
    return PRIORITY_RANK.get(Priority(raw), _UNRATED_RANK)


def default_key(item: QueueItem) -> tuple:
    """The default rule (FR-37): priority, then due date (none last), then how
    often it was reported (more first), then age (oldest first). The id breaks
    a tie on every key, so the order is total."""
    return (
        priority_rank(item.priority),
        item.due_date or date.max,
        -item.recurrence_count,
        item.created_at,
        item.issue_id,
    )


def insertion_index(new_item: QueueItem, rest: Sequence[QueueItem]) -> int:
    """Where ``new_item`` enters ``rest`` (in manual order): the index of the
    first item whose default key is greater than the new item's, else the end."""
    key = default_key(new_item)
    for index, item in enumerate(rest):
        if item.issue_id != new_item.issue_id and default_key(item) > key:
            return index
    return len(rest)


def position_at(
    positions: Sequence[float], index: int, *, dormant: Sequence[float] = (),
) -> float | None:
    """A position that sorts at ``index`` among the ascending ``positions``.

    ``dormant`` are the positions of dormant entries in the same group: never
    shown, but a new position must not collide with one, or a returning item
    would lose its place. The result lands directly above ``positions[index]``,
    below any dormant position between it and its visible neighbour.

    ``None`` means the neighbours are too close for a midpoint — renumber the
    group (``renumbered``) and ask again.
    """
    everything = sorted([*positions, *dormant])
    if not everything:
        return POSITION_STEP
    if index >= len(positions):
        return everything[-1] + POSITION_STEP
    upper = positions[max(index, 0)]
    below = [p for p in everything if p < upper]
    if not below:
        return upper - POSITION_STEP
    lower = below[-1]
    if (upper - lower) / 2 < MIN_GAP:
        return None
    return (lower + upper) / 2


def renumbered(count: int) -> list[float]:
    """Fresh, evenly spaced positions for a group of ``count`` entries."""
    return [POSITION_STEP * (i + 1) for i in range(count)]


def ordered(items: Sequence[QueueItem]) -> list[QueueItem]:
    """The full queue order: pinned, then rest, each by position (id breaks ties)."""
    return sorted(items, key=lambda i: (not i.pinned, i.position, i.issue_id))


def absolute_index(items: Sequence[QueueItem], issue_id: int) -> int | None:
    """1-based place of ``issue_id`` in the full queue (queue history, BR-44)."""
    for index, item in enumerate(ordered(items), start=1):
        if item.issue_id == issue_id:
            return index
    return None


def move_index(
    items: Sequence[QueueItem],
    issue_id: int,
    *,
    before_id: int | None = None,
    after_id: int | None = None,
) -> int:
    """Where ``issue_id`` lands in its own group when dropped directly before
    ``before_id`` or directly after ``after_id`` — an index into the group
    *without* the moved item.

    Refuses a move across the pinned/rest boundary (``queue_group_boundary``):
    pinning is how an item is lifted, not dragging.
    """
    if (before_id is None) == (after_id is None):
        raise QueueRuleError("invalid_move", "Say which item to place it before or after.")
    by_id = {i.issue_id: i for i in items}
    moving = by_id.get(issue_id)
    anchor_id = before_id if before_id is not None else after_id
    anchor = by_id.get(anchor_id)
    if moving is None or anchor is None:
        raise QueueRuleError("not_in_queue", "That item isn't in this queue.")
    if anchor.pinned != moving.pinned:
        detail = (
            "Pinned items stay above the rest. Pin an item to lift it into Pinned."
            if not moving.pinned
            else "A pinned item stays in Pinned. Unpin it to move it into the rest of the queue."
        )
        raise QueueRuleError("queue_group_boundary", detail)
    group = [i for i in ordered(items) if i.pinned == moving.pinned and i.issue_id != issue_id]
    if anchor_id == issue_id:
        # Dropped on itself — stays where it is.
        before = [i for i in ordered(items) if i.pinned == moving.pinned]
        return [i.issue_id for i in before].index(issue_id)
    index = [i.issue_id for i in group].index(anchor_id)
    return index if before_id is not None else index + 1
