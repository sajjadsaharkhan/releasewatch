"""Workflow — the single source of allowed status transitions.

A pure module: it takes plain values in (item type, current status, target
status, and a context dict) and returns plain values out. No database or
HTTP access — every caller (``IssueService.transition``, the API layer
building ``allowed_transitions``) supplies its own context.

Bug status movement is intentionally unrestricted: a user can move a bug to
any status from any status via the generic ``/transition`` endpoint (and the
status control in the UI) — including skipping steps, verifying your own
fix, and cancelling without a reason. This module still exists as the single
place that decision lives (rather than being duplicated per caller), and
``IssueService.regress()`` still asks it before recording a regression, so
loosening or re-tightening the rule later only touches this file.

Tasks (slice 03, docs/phase-2/03-tasks-and-placement.md) are a separate,
newly-introduced item type and follow the gated table in that spec — the
2026-09-22 decision to unrestrict movement was scoped to bugs only and is
not extended to tasks here. ``new``/``needs_info`` are bug-only (BR-10) and
are never offered to tasks.

Both item types share one rule: a ``cancelled`` target's ``cancel_reason``
must be valid for the type (BR-13) — ``no_longer_needed`` is task-only, every
other reason is bug-only.
"""

from dataclasses import dataclass, field
from typing import Any

from app.db.models.issue import (
    BUG_CANCEL_REASONS,
    IssueCancelReason,
    IssueStatus,
    TASK_CANCEL_REASONS,
)


@dataclass
class TransitionCheck:
    """Result of ``Workflow.can_transition``."""

    ok: bool
    code: str | None = None
    detail: str | None = None
    allowed: list[str] = field(default_factory=list)


@dataclass
class WorkflowTargets:
    """Result of ``Workflow.allowed_targets`` — for building an API response."""

    allowed: list[str]
    blocked: list[dict[str, str]]


def _as_status(value: Any) -> IssueStatus:
    return value if isinstance(value, IssueStatus) else IssueStatus(value)


_BUG_CANCEL_REASON_VALUES = {r.value for r in BUG_CANCEL_REASONS}
_TASK_CANCEL_REASON_VALUES = {r.value for r in TASK_CANCEL_REASONS}

#: Task transition table (docs/phase-2/03-tasks-and-placement.md). Keyed by
#: current status; ``blocked``'s target set is completed at lookup time from
#: the issue's own ``blocked_from_status``.
_TASK_STATIC_TARGETS: dict[IssueStatus, set[IssueStatus]] = {
    IssueStatus.todo: {IssueStatus.in_progress, IssueStatus.blocked, IssueStatus.cancelled},
    IssueStatus.in_progress: {
        IssueStatus.in_review, IssueStatus.done, IssueStatus.blocked, IssueStatus.cancelled,
    },
    IssueStatus.in_review: {
        IssueStatus.done, IssueStatus.in_progress, IssueStatus.blocked, IssueStatus.cancelled,
    },
    IssueStatus.blocked: {IssueStatus.cancelled},
    IssueStatus.done: set(),
    IssueStatus.cancelled: set(),
}


def _task_targets(from_status: IssueStatus, context: dict[str, Any] | None) -> set[IssueStatus]:
    targets = set(_TASK_STATIC_TARGETS.get(from_status, set()))
    if from_status == IssueStatus.blocked:
        blocked_from = (context or {}).get("blocked_from_status")
        targets.add(_as_status(blocked_from) if blocked_from else IssueStatus.todo)
    return targets


def _cancel_reason_error(item_type: str, context: dict[str, Any] | None) -> TransitionCheck | None:
    """Return a refusal if ``context['cancel_reason']`` isn't valid for ``item_type``.

    ``None`` means the reason is valid (or, for a bug, simply absent — a bug
    doesn't require a reason to cancel, per the 2026-09-22 decision).
    """
    raw = (context or {}).get("cancel_reason")
    reason = raw.value if isinstance(raw, IssueCancelReason) else raw
    if item_type == "task":
        if reason not in _TASK_CANCEL_REASON_VALUES:
            return TransitionCheck(
                False, code="invalid_cancel_reason",
                detail="A task can only be cancelled with reason 'no_longer_needed'.",
                allowed=[],
            )
        return None
    if reason is not None and reason not in _BUG_CANCEL_REASON_VALUES:
        return TransitionCheck(
            False, code="invalid_cancel_reason",
            detail="'no_longer_needed' is a task-only cancel reason.",
            allowed=[],
        )
    return None


class Workflow:
    """Bugs: every status is reachable from every other. Tasks: a gated table."""

    @staticmethod
    def allowed_targets(
        item_type: str, from_status: Any, context: dict[str, Any] | None = None,
    ) -> WorkflowTargets:
        """Return the statuses reachable from ``from_status`` — used to build
        ``IssueResponse.allowed_transitions``.
        """
        from_st = _as_status(from_status)
        if item_type == "bug":
            return WorkflowTargets(
                allowed=[s.value for s in IssueStatus if s != from_st],
                blocked=[],
            )
        if item_type == "task":
            return WorkflowTargets(
                allowed=[s.value for s in _task_targets(from_st, context)],
                blocked=[],
            )
        return WorkflowTargets(allowed=[], blocked=[])

    @staticmethod
    def can_transition(
        item_type: str,
        from_status: Any,
        to_status: Any,
        context: dict[str, Any] | None = None,
    ) -> TransitionCheck:
        if item_type not in ("bug", "task"):
            return TransitionCheck(
                False, code="invalid_transition",
                detail=f"Unknown item type '{item_type}'.", allowed=[],
            )
        from_st = _as_status(from_status)
        to_st = _as_status(to_status)
        if item_type == "bug" and to_st == from_st:
            # A bug can re-enter its own status (e.g. the regression action
            # on an already-in_progress bug) — unrestricted movement (the
            # 2026-09-22 decision) includes the identity move.
            return TransitionCheck(True, allowed=Workflow.allowed_targets(item_type, from_st, context).allowed)
        targets = Workflow.allowed_targets(item_type, from_st, context)
        if to_st.value not in targets.allowed:
            return TransitionCheck(
                False, code="invalid_transition",
                detail=f"Cannot move from '{from_st.value}' to '{to_st.value}'.",
                allowed=targets.allowed,
            )
        if to_st == IssueStatus.cancelled:
            cancel_error = _cancel_reason_error(item_type, context)
            if cancel_error is not None:
                cancel_error.allowed = targets.allowed
                return cancel_error
        return TransitionCheck(True, allowed=targets.allowed)
