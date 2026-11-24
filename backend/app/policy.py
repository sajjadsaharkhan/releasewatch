"""Policy — who may do what (slice 04, PRD §7.3 and §9.2).

A pure module, like ``app/workflow.py``: plain values in, plain values out,
no database or HTTP access. ``decide(actor, action, target)`` answers "can
this user do this action on this item or project, and if not, why".

Policy and Workflow compose: Policy says whether an actor may *attempt* an
action; Workflow says whether a status move is *legal*. Routes check Policy,
services check Workflow.

The §7.3 matrix is transcribed once, as data, in ``MATRIX``. Rules that
depend on the item (visibility, the per-project triage lead, assignability)
are the small predicates below it. Self-verification (AC-27) is deliberately
absent — removed by the 2026-09-22 product decision, see CONTEXT.md.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Role(str, Enum):
    """Mirror of ``UserRole`` values — kept here so Policy imports no ORM."""

    support = "support"
    qa = "qa"
    developer = "developer"
    product_manager = "product_manager"
    cto = "cto"
    admin = "admin"


#: Everyone except Support (§7.1).
TECH_ROLES: frozenset[str] = frozenset({"qa", "developer", "product_manager", "cto", "admin"})
#: Who can be given work (BR-32) — the tech roles; never Support.
ASSIGNABLE_ROLES: frozenset[str] = TECH_ROLES
ALL_ROLES: frozenset[str] = frozenset(r.value for r in Role)


class Action(str, Enum):
    """The closed set of actions Policy decides; ``transition()`` builds ``transition:<to>``."""

    view_item = "view_item"
    comment_public = "comment_public"
    comment_internal = "comment_internal"
    create_item = "create_item"
    edit_item = "edit_item"
    assign = "assign"
    set_priority = "set_priority"
    set_due_date = "set_due_date"
    flag_release_blocker = "flag_release_blocker"
    reject = "reject"
    #: Verified → Done for Stream items, one or many at once (v3.1, BR-68).
    mark_production = "mark_production"
    flag_tech_debt = "flag_tech_debt"
    triage = "triage"
    view_duplicate_hints = "view_duplicate_hints"
    report_recurrence = "report_recurrence"
    #: Problem is back (v3.1, FR-68): Support's request on a Done item.
    request_return = "request_return"
    #: Confirm or dismiss a return request (FR-69) — anyone who can triage.
    decide_return_request = "decide_return_request"
    submit_support_report = "submit_support_report"
    manage_templates = "manage_templates"
    #: A project's Support channel — the Telegram topic (v3.1, FR-70).
    manage_support_channel = "manage_support_channel"
    manage_backlog_categories = "manage_backlog_categories"
    view_backlog = "view_backlog"
    manage_backlog = "manage_backlog"
    manage_releases = "manage_releases"
    ship_release = "ship_release"
    view_queue = "view_queue"
    #: The To review tab: every item in review, in every project (v3.1, FR-73).
    view_review_queue = "view_review_queue"
    reorder_queue = "reorder_queue"
    pin = "pin"
    view_team_overview = "view_team_overview"
    view_reports = "view_reports"
    view_releases = "view_releases"
    go_nogo = "go_nogo"
    manage_users = "manage_users"
    manage_projects = "manage_projects"
    manage_search = "manage_search"
    use_mcp = "use_mcp"
    manage_mcp_tokens = "manage_mcp_tokens"


TRANSITION_PREFIX = "transition:"


def transition(to: Any) -> str:
    """The action name for moving an item to status ``to``."""
    return f"{TRANSITION_PREFIX}{getattr(to, 'value', to)}"


# ── Inputs and outputs ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Actor:
    id: int
    role: str


@dataclass(frozen=True)
class Target:
    """A plain snapshot of whatever the action is about. Every field is optional."""

    item_id: int | None = None
    item_type: str | None = None
    status: str | None = None
    #: ``stream`` / ``release`` / ``None`` (the backlog) — the item's container (v3.1).
    container_kind: str | None = None
    source: str | None = None  # internal | support (slice 05)
    #: Who is subscribed to the item's Support notices (slice 06) — a Support
    #: subscriber may view it even when it isn't support-sourced.
    subscriber_ids: frozenset[int] = frozenset()
    assignee_id: int | None = None
    reporter_id: int | None = None
    project_id: int | None = None
    triage_lead_id: int | None = None
    queue_owner_id: int | None = None
    assignee_role: str | None = None  # for ``assign``: the role of the proposed assignee


@dataclass(frozen=True)
class Allowed:
    ok: bool = True


@dataclass(frozen=True)
class Denied:
    code: str
    detail: str
    #: True when the UI should not render the control at all (Support never
    #: sees tech-only controls, §7.3) rather than show it disabled.
    hidden: bool = False
    #: True when the actor may not even know the item exists — routes answer 404.
    not_found: bool = False
    #: True when the refusal is a domain rule about the item's state, not about
    #: who the actor is — routes answer 409 instead of 403 (slice 07).
    conflict: bool = False
    ok: bool = False


Decision = Allowed | Denied

ALLOWED = Allowed()


# ── The §7.3 matrix (plus the §9.2 flag rules) ────────────────────────────────

#: Pseudo-role: the actor is the target project's triage lead (any tech role).
TRIAGE_LEAD = "triage_lead"
#: Pseudo-role: a developer who is the target project's triage lead (§7.3 footnote ²).
DEVELOPER_AS_LEAD = "developer_as_lead"

_T = TECH_ROLES
_CTO_ADMIN = frozenset({"cto", "admin"})
_MANAGE = frozenset({"product_manager", "cto", "admin", DEVELOPER_AS_LEAD})

MATRIX: dict[str, frozenset[str]] = {
    # §7.3
    Action.submit_support_report: frozenset({"support", "admin"}),
    Action.create_item: _T,
    Action.view_item: ALL_ROLES,  # narrowed for Support by _can_view
    Action.comment_public: ALL_ROLES,
    Action.comment_internal: _T,
    Action.report_recurrence: ALL_ROLES,
    Action.request_return: frozenset({"support"}),
    Action.decide_return_request: _T,
    Action.triage: _T,
    # 14: triage merge hints are tech-only; Support never sees them (FR-S13).
    Action.view_duplicate_hints: _T,
    TRANSITION_PREFIX: _T,  # every transition:<to>, verification included
    Action.flag_tech_debt: _T,
    Action.view_backlog: _T,  # the backlog and Technical debt pages (slice 08)
    Action.manage_backlog: _MANAGE,
    Action.manage_releases: _MANAGE,
    # Slice 09 (FR-53): CTO, Admin, and the project's triage lead of any tech role;
    # PM added 2026-11-22.
    Action.ship_release: frozenset({"product_manager", "cto", "admin", TRIAGE_LEAD}),
    Action.view_queue: _T,  # own queue; someone else's is CTO/Admin (decide)
    Action.view_review_queue: _T,
    Action.reorder_queue: _T,
    Action.pin: _T,
    Action.view_team_overview: _CTO_ADMIN,
    Action.go_nogo: frozenset({"product_manager", "cto", "admin"}),  # PM added 2026-11-22
    Action.manage_templates: _CTO_ADMIN,
    Action.manage_support_channel: _CTO_ADMIN,
    Action.manage_backlog_categories: _CTO_ADMIN,  # Settings → Backlog categories (2026-09-28)
    # CTO has everything Admin has in Settings (2026-10-05).
    Action.manage_users: _CTO_ADMIN,
    Action.manage_projects: _CTO_ADMIN,
    Action.manage_search: _CTO_ADMIN,
    # Slice 15 (BR-M04): MCP is for the tech team; Settings → MCP (the switch
    # and everyone's tokens) follows the CTO-has-what-Admin-has rule.
    Action.use_mcp: _T,
    Action.manage_mcp_tokens: _CTO_ADMIN,
    # Field edits on an item a tech user can see.
    Action.edit_item: _T,
    Action.assign: _T,
    Action.set_priority: _T,
    Action.set_due_date: _T,
    Action.view_reports: _T,
    Action.view_releases: _T,
    # §9.2 flags
    Action.flag_release_blocker: frozenset({"qa", "product_manager", "cto", "admin", TRIAGE_LEAD}),
    # 09a: Reject delivered or Done work — every tech role, never Support.
    Action.reject: _T,
    # v3.1 (BR-68): the person who deploys moves Verified Stream items to Done.
    Action.mark_production: _T,
}

#: Actions about a specific item — visibility is checked before the matrix.
_ITEM_ACTIONS = frozenset({
    Action.view_item, Action.comment_public, Action.comment_internal, Action.edit_item,
    Action.assign, Action.set_priority, Action.set_due_date, Action.flag_release_blocker,
    Action.reject, Action.mark_production, Action.flag_tech_debt, Action.triage,
    Action.report_recurrence, Action.request_return, Action.decide_return_request,
})

_QUEUE_ACTIONS = frozenset({Action.view_queue, Action.reorder_queue, Action.pin})

#: Human-readable name per action, for the disabled-control tooltip.
_LABELS: dict[str, str] = {
    Action.submit_support_report: "submit a support report",
    Action.create_item: "file bugs or tasks",
    Action.comment_internal: "post internal notes",
    Action.triage: "triage",
    Action.flag_tech_debt: "flag technical debt",
    Action.view_backlog: "view the backlog",
    Action.manage_backlog: "manage the backlog",
    Action.manage_releases: "manage releases",
    Action.ship_release: "ship releases",
    # Only reached for someone else's queue — every tech role has their own (slice 10).
    Action.view_queue: "view other people's queues",
    Action.view_review_queue: "see what is waiting for review",
    Action.reorder_queue: "reorder other people's queues",
    Action.pin: "pin items in other people's queues",
    Action.view_team_overview: "view the team overview",
    Action.go_nogo: "make the release go/no-go call",
    Action.manage_templates: "manage templates",
    Action.manage_support_channel: "manage the Support channel",
    Action.manage_backlog_categories: "manage backlog categories",
    Action.manage_users: "manage users",
    Action.manage_projects: "manage projects",
    Action.manage_search: "manage search settings",
    Action.use_mcp: "connect coding agents over MCP",
    Action.manage_mcp_tokens: "manage MCP settings",
    Action.edit_item: "edit items",
    Action.assign: "assign items",
    Action.set_priority: "set priority",
    Action.set_due_date: "set due dates",
    Action.view_reports: "view reports",
    Action.view_releases: "view releases",
    Action.flag_release_blocker: "flag release blockers",
    Action.reject: "reject work",
    Action.mark_production: "mark work as on production",
    Action.request_return: "ask for a Done item to come back",
    Action.decide_return_request: "decide return requests",
}

_ROLE_LABELS = {
    "support": "Support", "qa": "QA", "developer": "Developers", "product_manager": "Product Managers",
    "cto": "CTOs", "admin": "Admins",
}


def _role(value: Any) -> str:
    return getattr(value, "value", value)


# ── Predicates ────────────────────────────────────────────────────────────────


def is_tech(role: Any) -> bool:
    return _role(role) in TECH_ROLES


def is_assignable(role: Any) -> bool:
    """BR-32 — Support users are never assignable."""
    return _role(role) in ASSIGNABLE_ROLES


def _can_view(actor: Actor, target: Target) -> bool:
    """BR-30 — Support sees support-sourced items, plus items they're subscribed to
    (a report merged into an internal original, 2026-09-24 decision); everyone
    else sees everything."""
    if _role(actor.role) == Role.support.value:
        return target.source == "support" or actor.id in target.subscriber_ids
    return True


def _is_lead(actor: Actor, target: Target) -> bool:
    return target.triage_lead_id is not None and target.triage_lead_id == actor.id


def _matrix_allows(actor: Actor, roles: frozenset[str], target: Target) -> bool:
    role = _role(actor.role)
    if role in roles:
        return True
    if TRIAGE_LEAD in roles and role in TECH_ROLES and _is_lead(actor, target):
        return True
    if DEVELOPER_AS_LEAD in roles and role == Role.developer.value and _is_lead(actor, target):
        return True
    return False


def _deny_role(actor: Actor, action: str, roles: frozenset[str]) -> Denied:
    role = _role(actor.role)
    label = _LABELS.get(action, "do this")
    if action.startswith(TRANSITION_PREFIX):
        label = "change status"
    if role == Role.support.value:
        # Tech-only controls are never shown to Support (§7.3), whatever the rule.
        return Denied("forbidden_role", f"Support can't {label}.", hidden=True)
    if role == Role.developer.value and DEVELOPER_AS_LEAD in roles:
        return Denied(
            "not_triage_lead",
            f"Only this project's triage lead can {label} as a developer.",
        )
    if TRIAGE_LEAD in roles:
        return Denied(
            "not_triage_lead",
            f"{_ROLE_LABELS.get(role, role)} can {label} only as this project's triage lead.",
        )
    return Denied("forbidden_role", f"{_ROLE_LABELS.get(role, role)} can't {label}.")


#: FR-16 / BR-23 — shown on the disabled Report recurrence button of a Done bug.
RECURRENCE_ON_DONE_DETAIL = (
    "This item is Done. Use Problem is back to ask for it to come back."
)


def _recurrence_denial(target: Target) -> Denied | None:
    """FR-13/16 — a recurrence goes on an open or Cancelled bug, never a task or a Done bug."""
    if target.item_type is not None and target.item_type != "bug":
        return Denied(
            "recurrence_bug_only", "Recurrences can be reported on bugs only.",
            hidden=True, conflict=True,
        )
    if target.status == "done":
        return Denied("recurrence_on_done", RECURRENCE_ON_DONE_DETAIL, conflict=True)
    return None


#: Where Reject is offered (09a, v3.1) — ``REJECTABLE_STATUSES`` as plain values.
_REJECTABLE = frozenset({"to_review", "in_review", "verified", "done"})


def _reject_denial(target: Target) -> Denied | None:
    """09a — only delivered (To review, In review), Verified or Done work can be
    rejected; elsewhere the control doesn't exist."""
    if target.status is not None and target.status not in _REJECTABLE:
        return Denied(
            "not_rejectable", "Only work in review, Verified or Done can be rejected.",
            hidden=True, conflict=True,
        )
    return None


#: Statuses where Support verifies or rejects a support-sourced item (BR-71).
_SUPPORT_REVIEW_STATUSES = frozenset({"to_review", "in_review"})


def _support_status_move(actor: Actor, action: str, target: Target) -> Decision:
    """BR-71 — the only status moves Support makes: on a support-sourced item in
    To review / In review, Verified (or Done in the Stream) and Reject. Anything
    else is a hidden denial, like every tech-only control (§7.3)."""
    denied = Denied("forbidden_role", "Support can't change status.", hidden=True)
    if target.source != "support" or target.status not in _SUPPORT_REVIEW_STATUSES:
        return denied
    if action == Action.reject.value:
        return ALLOWED
    to = action[len(TRANSITION_PREFIX):]
    if to == "verified":
        return ALLOWED
    if to == "done":
        if target.container_kind == "stream":
            return ALLOWED
        if target.container_kind == "release":
            return Denied(
                "done_at_ship", "Done when the release ships.", hidden=True, conflict=True,
            )
    return denied


def _request_return_denial(actor: Actor, target: Target) -> Denied | None:
    """FR-68 — Problem is back is Support's, on a Done item; no control for tech roles."""
    if _role(actor.role) != Role.support.value:
        return Denied(
            "forbidden_role", "Only Support can ask for a Done item to come back.", hidden=True,
        )
    if target.status != "done":
        return Denied(
            "not_done", "Problem is back applies to Done items only.", hidden=True, conflict=True,
        )
    return None


def _production_denial(target: Target) -> Denied | None:
    """BR-68 — On production applies to Verified items of the Stream; elsewhere
    the control doesn't exist (a release item becomes Done at ship)."""
    if (target.status is not None and target.status != "verified") or (
        target.container_kind is not None and target.container_kind != "stream"
    ):
        return Denied(
            "not_verified_in_stream",
            "Only a Verified item in the Stream can be put on production.",
            hidden=True, conflict=True,
        )
    return None


def _tech_debt_denial(target: Target) -> Denied | None:
    """BR-36 — technical debt is always a task; the flag doesn't exist on bugs (AC-31)."""
    if target.item_type is not None and target.item_type != "task":
        return Denied(
            "tech_debt_task_only", "Only tasks can be flagged as technical debt.",
            hidden=True, conflict=True,
        )
    return None


# ── Public entry point ────────────────────────────────────────────────────────


def decide(actor: Actor, action: Any, target: Target | None = None) -> Decision:
    """``Allowed``, or ``Denied(code, detail)`` saying why ``actor`` can't do ``action``."""
    target = target or Target()
    action = getattr(action, "value", action)
    key = TRANSITION_PREFIX if action.startswith(TRANSITION_PREFIX) else action
    if key == TRANSITION_PREFIX:
        roles = MATRIX[TRANSITION_PREFIX]
    else:
        try:
            roles = MATRIX[Action(action)]
        except ValueError:
            return Denied("unknown_action", f"Unknown action '{action}'.")

    if (key == TRANSITION_PREFIX or key in _ITEM_ACTIONS) and target.item_id is not None:
        if not _can_view(actor, target):
            return Denied("not_found", "Issue not found", hidden=True, not_found=True)

    if key in _QUEUE_ACTIONS and target.queue_owner_id not in (None, actor.id):
        roles = _CTO_ADMIN

    if key == Action.request_return:
        return _request_return_denial(actor, target) or ALLOWED

    # Support verifies and rejects what it filed (BR-71) and makes no other move.
    if _role(actor.role) == Role.support.value and (
        key == TRANSITION_PREFIX or key == Action.reject
    ):
        return _support_status_move(actor, action, target)

    if not _matrix_allows(actor, roles, target):
        return _deny_role(actor, action, roles)

    if (
        key == Action.assign
        and target.assignee_role is not None
        and not is_assignable(target.assignee_role)
    ):
        return Denied("not_assignable", "Support users can't be assigned work.")

    if key == Action.report_recurrence:
        denial = _recurrence_denial(target)
        if denial is not None:
            return denial

    if key == Action.reject:
        denial = _reject_denial(target)
        if denial is not None:
            return denial

    if key == Action.mark_production:
        denial = _production_denial(target)
        if denial is not None:
            return denial

    if key == Action.flag_tech_debt:
        denial = _tech_debt_denial(target)
        if denial is not None:
            return denial

    return ALLOWED


def allows(actor: Actor, action: Any, target: Target | None = None) -> bool:
    return decide(actor, action, target).ok


#: Item actions reported on every ``IssueResponse`` (``allowed_actions`` / ``blocked_actions``).
RESPONSE_ITEM_ACTIONS: tuple[str, ...] = (
    Action.comment_public.value,
    Action.comment_internal.value,
    Action.edit_item.value,
    Action.assign.value,
    Action.set_priority.value,
    Action.set_due_date.value,
    Action.triage.value,
    Action.flag_release_blocker.value,
    Action.reject.value,
    Action.mark_production.value,
    Action.report_recurrence.value,
    Action.request_return.value,
    Action.decide_return_request.value,
    # The item page's hints block keys off this, never the role (14, FR-S13).
    Action.view_duplicate_hints.value,
)


def item_actions(
    actor: Actor, target: Target, workflow_targets: list[str],
) -> tuple[list[str], list[dict[str, str]]]:
    """Run Policy over every action relevant to one item.

    ``workflow_targets`` are the statuses Workflow says are reachable; each
    becomes a ``transition:<to>`` action. Returns ``(allowed, blocked)``;
    hidden denials (Support + tech-only controls) appear in neither list.
    """
    allowed: list[str] = []
    blocked: list[dict[str, str]] = []
    actions = list(RESPONSE_ITEM_ACTIONS)
    if target.item_type == "task":
        actions.append(Action.flag_tech_debt.value)
    actions += [transition(s) for s in workflow_targets]
    for action in actions:
        d = decide(actor, action, target)
        if d.ok:
            allowed.append(action)
        elif not d.hidden:
            blocked.append({"action": action, "code": d.code, "detail": d.detail})
    return allowed, blocked
