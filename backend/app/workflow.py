"""Workflow — the single source of allowed status transitions.

A pure module: it takes plain values in (item type, current status, target
status, and a context dict) and returns plain values out. No database or
HTTP access — every caller (``IssueService.transition``, the API layer
building ``allowed_transitions``) supplies its own context.

Only "bug" transitions exist as of slice 02 (docs/phase-2/02-unified-status-model.md).
Tasks arrive in slice 03 and will extend ``_TARGETS_BY_TYPE``.

Context keys used:
    actor_id                 — who is attempting the transition
    review_requested_by_id   — issue.review_requested_by_id
    blocked_from_status      — issue.blocked_from_status
    has_release               — issue.release_id is not None
    release_shipped          — release.status in (released, archived)
    cancel_reason            — the reason supplied for a cancel transition
    reason                   — free-form reason (e.g. "merge_regression")
    via_triage                — set only by IssueService.triage()
    via_needs_info            — set only by IssueService.needs_clarification()
    via_regression            — set only by IssueService.regress()
"""

from dataclasses import dataclass, field
from typing import Any

from app.db.models.issue import IssueStatus

_CANCEL_SOURCES = (IssueStatus.new, IssueStatus.todo, IssueStatus.needs_info, IssueStatus.blocked)
_BLOCK_SOURCES = (IssueStatus.todo, IssueStatus.in_progress, IssueStatus.in_review)


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


def _bug_targets(from_status: IssueStatus, context: dict[str, Any]) -> WorkflowTargets:
    """The generic, actor-independent transition graph for a bug.

    Excludes ``new -> todo`` / ``new -> needs_info`` (only reachable through
    the triage outcome, see ``can_transition``) and ``done -> in_progress``
    (only reachable through the regression action).
    """
    actor_id = context.get("actor_id")
    review_requested_by_id = context.get("review_requested_by_id")
    blocked_from_status = context.get("blocked_from_status")

    allowed: list[str] = []
    blocked: list[dict[str, str]] = []

    if from_status in _CANCEL_SOURCES:
        allowed.append(IssueStatus.cancelled.value)

    if from_status == IssueStatus.needs_info:
        allowed.append(IssueStatus.new.value)

    if from_status == IssueStatus.todo:
        allowed.append(IssueStatus.in_progress.value)

    if from_status == IssueStatus.in_progress:
        allowed.append(IssueStatus.in_review.value)

    if from_status == IssueStatus.in_review:
        if (
            review_requested_by_id is not None
            and actor_id is not None
            and str(review_requested_by_id) == str(actor_id)
        ):
            blocked.append({
                "to": IssueStatus.done.value,
                "code": "self_verification",
                "detail": "You moved this to review yourself and can't verify your own fix.",
            })
        else:
            allowed.append(IssueStatus.done.value)
        allowed.append(IssueStatus.in_progress.value)

    if from_status in _BLOCK_SOURCES:
        allowed.append(IssueStatus.blocked.value)

    if from_status == IssueStatus.blocked:
        allowed.append(IssueStatus.todo.value)
        if blocked_from_status and blocked_from_status != IssueStatus.todo.value:
            allowed.append(blocked_from_status)

    # Stable order, no duplicates.
    seen: list[str] = []
    for target in allowed:
        if target not in seen:
            seen.append(target)
    return WorkflowTargets(allowed=seen, blocked=blocked)


class Workflow:
    """Every allowed status transition, and the reason a transition is refused."""

    @staticmethod
    def allowed_targets(
        item_type: str, from_status: Any, context: dict[str, Any] | None = None,
    ) -> WorkflowTargets:
        """Return the transitions reachable from ``from_status`` via the generic endpoint.

        Used to build ``IssueResponse.allowed_transitions`` / ``blocked_transitions``.
        Does not include triage-outcome or regression-action targets — those
        keep their own endpoints and are not part of this display graph.
        """
        if item_type != "bug":
            return WorkflowTargets(allowed=[], blocked=[])
        return _bug_targets(_as_status(from_status), context or {})

    @staticmethod
    def can_transition(
        item_type: str,
        from_status: Any,
        to_status: Any,
        context: dict[str, Any] | None = None,
    ) -> TransitionCheck:
        """Decide whether ``from_status -> to_status`` is allowed right now."""
        ctx = context or {}
        from_st = _as_status(from_status)
        to_st = _as_status(to_status)

        if item_type != "bug":
            return TransitionCheck(
                False, code="invalid_transition",
                detail=f"Unknown item type '{item_type}'.", allowed=[],
            )

        targets = _bug_targets(from_st, ctx)

        # ── The regression action's release gate, checked first ────────────────
        # Applies uniformly whether flagged from Done or from In review (BR-24),
        # so it must run before the generic allowed-list fast path below — from
        # in_review, in_progress is already unconditionally allowed there (the
        # ordinary verify-fail path), which would otherwise let a regression
        # through against a shipped release. Workflow stays the single source
        # of this rule; IssueService.regress() only asks it.
        if to_st == IssueStatus.in_progress and ctx.get("via_regression"):
            if from_st not in (IssueStatus.done, IssueStatus.in_review):
                return TransitionCheck(
                    False, code="invalid_transition",
                    detail=f"Cannot record a regression from status '{from_st.value}'.",
                    allowed=targets.allowed,
                )
            if not ctx.get("has_release") or ctx.get("release_shipped"):
                no_release = not ctx.get("has_release")
                return TransitionCheck(
                    False, code="no_release" if no_release else "release_shipped",
                    detail="A regression can only be recorded against a release "
                           "that hasn't shipped.",
                    allowed=targets.allowed,
                )
            return TransitionCheck(True, allowed=targets.allowed)

        if to_st.value in targets.allowed:
            if to_st == IssueStatus.cancelled and not ctx.get("cancel_reason"):
                return TransitionCheck(
                    False, code="cancel_reason_required",
                    detail="A cancel reason is required.", allowed=targets.allowed,
                )
            return TransitionCheck(True, allowed=targets.allowed)

        for entry in targets.blocked:
            if entry["to"] == to_st.value:
                return TransitionCheck(
                    False, code=entry["code"], detail=entry["detail"], allowed=targets.allowed,
                )

        # ── Gated pairs, not part of the generic display graph ─────────────────
        if from_st == IssueStatus.new and to_st == IssueStatus.todo:
            if ctx.get("via_triage"):
                return TransitionCheck(True, allowed=targets.allowed)
            return TransitionCheck(
                False, code="invalid_transition",
                detail="New bugs move to To do only through triage.", allowed=targets.allowed,
            )

        if from_st == IssueStatus.new and to_st == IssueStatus.needs_info:
            if ctx.get("via_needs_info"):
                return TransitionCheck(True, allowed=targets.allowed)
            return TransitionCheck(
                False, code="invalid_transition",
                detail="New bugs move to Needs info only through triage.", allowed=targets.allowed,
            )

        if from_st == IssueStatus.done and to_st == IssueStatus.in_progress:
            if ctx.get("reason") == "merge_regression":
                return TransitionCheck(
                    False, code="use_triage",
                    detail="Merge regressions are handled by the merge workflow.",
                    allowed=targets.allowed,
                )
            return TransitionCheck(
                False, code="invalid_transition",
                detail="Done bugs return to In progress only through the regression action.",
                allowed=targets.allowed,
            )

        return TransitionCheck(
            False, code="invalid_transition",
            detail=f"Cannot move from {from_st.value} to {to_st.value}.",
            allowed=targets.allowed,
        )
