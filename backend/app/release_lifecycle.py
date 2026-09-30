"""Release lifecycle — the allowed release status changes (slice 09, PRD FR-50).

A pure module, beside ``app/workflow.py`` and separate from it: plain values
in, plain values out, no database or HTTP access. ``ReleaseService`` asks it
before every release status change; the API reports ``allowed_transitions``
from it so the UI never re-derives the table.

| From                      | To          | How                                          |
|---------------------------|-------------|----------------------------------------------|
| Planning                  | Development | manual                                       |
| Development               | QA          | manual (code freeze)                         |
| QA                        | Development | manual (back to development)                 |
| QA                        | Released    | **Ship** only (``ReleaseService.ship``)      |
| Planning, Development, QA | Cancelled   | manual, only with no Done item (BR-55)       |

Released and Cancelled are final. The Stream has no lifecycle (FR-46).
"""

from dataclasses import dataclass, field

PLANNING = "planning"
DEVELOPMENT = "development"
QA = "qa"
RELEASED = "released"
CANCELLED = "cancelled"

STATUSES: tuple[str, ...] = (PLANNING, DEVELOPMENT, QA, RELEASED, CANCELLED)
FINAL: frozenset[str] = frozenset({RELEASED, CANCELLED})

#: Manual moves (the Ship and Cancel rows have their own conditions below).
_MANUAL: dict[str, frozenset[str]] = {
    PLANNING: frozenset({DEVELOPMENT}),
    DEVELOPMENT: frozenset({QA}),
    QA: frozenset({DEVELOPMENT}),
}

_LABELS = {
    PLANNING: "Planning", DEVELOPMENT: "Development", QA: "QA",
    RELEASED: "Released", CANCELLED: "Cancelled",
}


@dataclass(frozen=True)
class Check:
    ok: bool
    code: str | None = None
    detail: str | None = None
    allowed: list[str] = field(default_factory=list)


def _value(v) -> str | None:
    return getattr(v, "value", v)


def _targets(status: str, *, has_done_items: bool, via_ship: bool) -> list[str]:
    if status in FINAL:
        return []
    out = sorted(_MANUAL.get(status, ()), key=STATUSES.index)
    if status == QA and via_ship:
        out.append(RELEASED)
    if not has_done_items:
        out.append(CANCELLED)
    return out


def can_change(
    kind: str,
    from_status: str | None,
    to_status: str,
    *,
    has_done_items: bool = False,
    via_ship: bool = False,
) -> Check:
    """May a container of ``kind`` move from ``from_status`` to ``to_status``?

    ``via_ship`` is true only inside ``ReleaseService.ship`` — the one way to Released.
    ``has_done_items`` is whether the release holds a Done item (BR-55).
    """
    kind, from_status, to_status = _value(kind), _value(from_status), _value(to_status)
    if kind == "stream":
        return Check(
            False, "stream_immutable",
            "The Stream can't be edited, cancelled, archived, or deleted.",
        )
    allowed = allowed_targets(kind, from_status, has_done_items=has_done_items)
    if to_status not in STATUSES:
        return Check(False, "unknown_status", f"Unknown release status '{to_status}'.", allowed)
    if from_status in FINAL:
        return Check(
            False, "release_final",
            f"A {_LABELS[from_status]} release is final — its status can't change.",
            allowed,
        )
    if to_status == from_status:
        return Check(False, "no_change", f"The release is already {_LABELS[to_status]}.", allowed)
    if to_status == RELEASED:
        if from_status != QA:
            return Check(
                False, "ship_only_from_qa", "Only a release in QA can be shipped.", allowed,
            )
        if not via_ship:
            return Check(
                False, "use_ship",
                "A release becomes Released only by shipping it.", allowed,
            )
        return Check(True)
    if to_status == CANCELLED:
        if has_done_items:
            return Check(
                False, "release_has_done_items",
                "A release with a Done item can't be cancelled.", allowed,
            )
        return Check(True)
    if to_status not in _MANUAL.get(from_status, ()):
        return Check(
            False, "invalid_release_transition",
            f"A release can't move from {_LABELS[from_status]} to {_LABELS[to_status]}.",
            allowed,
        )
    return Check(True)


def allowed_targets(kind: str, status: str | None, *, has_done_items: bool = False) -> list[str]:
    """Statuses reachable by a manual status change (``POST /releases/{id}/status``
    and ``/cancel``). Released is never listed — it's the Ship action's."""
    if _value(kind) == "stream" or status is None:
        return []
    return _targets(_value(status), has_done_items=has_done_items, via_ship=False)


def can_ship(kind: str, status: str | None) -> Check:
    """Ship is available only on a release in QA (AC-62)."""
    return can_change(kind, status, RELEASED, via_ship=True)


def label(status: str | None) -> str:
    return _LABELS.get(_value(status), str(status))
