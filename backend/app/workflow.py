"""Workflow — the single source of allowed status transitions.

A pure module: it takes plain values in (item type, current status, target
status, and a context dict) and returns plain values out. No database or
HTTP access — every caller (``IssueService.transition``, the API layer
building ``allowed_transitions``) supplies its own context.

Status movement is intentionally unrestricted: a user can move a bug to any
status from any status via the generic ``/transition`` endpoint (and the
status control in the UI) — including skipping steps, verifying your own
fix, and cancelling without a reason. This module still exists as the single
place that decision lives (rather than being duplicated per caller), and
``IssueService.regress()`` still asks it before recording a regression, so
loosening or re-tightening the rule later only touches this file.

Only "bug" items exist as of slice 02 (docs/phase-2/02-unified-status-model.md).
Tasks arrive in slice 03.
"""

from dataclasses import dataclass, field
from typing import Any

from app.db.models.issue import IssueStatus


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


class Workflow:
    """Every status is reachable from every other status, for bugs."""

    @staticmethod
    def allowed_targets(
        item_type: str, from_status: Any, context: dict[str, Any] | None = None,
    ) -> WorkflowTargets:
        """Return every other status as reachable — used to build
        ``IssueResponse.allowed_transitions``. Nothing is ever blocked.
        """
        if item_type != "bug":
            return WorkflowTargets(allowed=[], blocked=[])
        from_st = _as_status(from_status)
        return WorkflowTargets(
            allowed=[s.value for s in IssueStatus if s != from_st],
            blocked=[],
        )

    @staticmethod
    def can_transition(
        item_type: str,
        from_status: Any,
        to_status: Any,
        context: dict[str, Any] | None = None,
    ) -> TransitionCheck:
        """Any ``from_status -> to_status`` move is allowed for a bug."""
        if item_type != "bug":
            return TransitionCheck(
                False, code="invalid_transition",
                detail=f"Unknown item type '{item_type}'.", allowed=[],
            )
        targets = Workflow.allowed_targets(item_type, from_status)
        return TransitionCheck(True, allowed=targets.allowed)
