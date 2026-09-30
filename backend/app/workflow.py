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

Tasks (slice 03) are unrestricted too, by the 2026-09-23 decision: a task can
move from any of its statuses to any other, including out of ``done`` and
``cancelled``. ``new``/``needs_info`` are bug-only (BR-10) and are never
offered to tasks.

Both item types share one rule: a cancel reason is optional, but when one is
given it must be valid for the type (BR-13) — ``no_longer_needed`` is
task-only, every other reason is bug-only.

The one exception to free movement (09a, ADR 0004): nothing enters
``rejected`` by a plain move (409 ``use_reject``), and ``allowed_targets``
never lists it. ``IssueService`` passes ``via_reject`` in the context when the
Reject action (or a merge into a Done item) moves the item there. Leaving
``rejected`` is free.
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

#: Every status a task can hold — the bug-only triage statuses are excluded (BR-10).
_TASK_STATUSES = tuple(
    s for s in IssueStatus if s not in (IssueStatus.new, IssueStatus.needs_info)
)


def _task_targets(from_status: IssueStatus) -> set[IssueStatus]:
    return {s for s in _TASK_STATUSES if s != from_status and s != IssueStatus.rejected}


def _cancel_reason_error(item_type: str, context: dict[str, Any] | None) -> TransitionCheck | None:
    """Return a refusal if ``context['cancel_reason']`` isn't valid for ``item_type``.

    ``None`` means the reason is valid or absent — neither type requires a
    reason to cancel (the 2026-09-22 decision, extended to tasks 2026-09-23).
    """
    raw = (context or {}).get("cancel_reason")
    reason = raw.value if isinstance(raw, IssueCancelReason) else raw
    if reason is None:
        return None
    if item_type == "task":
        if reason not in _TASK_CANCEL_REASON_VALUES:
            return TransitionCheck(
                False, code="invalid_cancel_reason",
                detail="A task can only be cancelled with reason 'no_longer_needed'.",
                allowed=[],
            )
        return None
    if reason not in _BUG_CANCEL_REASON_VALUES:
        return TransitionCheck(
            False, code="invalid_cancel_reason",
            detail="'no_longer_needed' is a task-only cancel reason.",
            allowed=[],
        )
    return None


class Workflow:
    """Every status is reachable from every other — for tasks, every task status."""

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
                allowed=[
                    s.value for s in IssueStatus
                    if s != from_st and s != IssueStatus.rejected
                ],
                blocked=[],
            )
        if item_type == "task":
            return WorkflowTargets(
                allowed=[s.value for s in _task_targets(from_st)],
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
        if to_st == IssueStatus.rejected:
            allowed = Workflow.allowed_targets(item_type, from_st, context).allowed
            if not (context or {}).get("via_reject"):
                return TransitionCheck(
                    False, code="use_reject",
                    detail="Use Reject to send work back — it needs a comment.",
                    allowed=allowed,
                )
            return TransitionCheck(True, allowed=allowed)
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
