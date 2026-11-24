"""Slice 04 — Policy unit tests (pure, no DB).

The expected table below is transcribed independently from PRD §7.3 and §9.2
so a typo in ``app/policy.py::MATRIX`` shows up as a disagreement here.
Rows whose screens arrive in later slices (support report, recurrence,
technical debt, queues, team overview, templates, search settings) are only
testable here until their endpoints exist.
"""

import pytest

from app import policy
from app.policy import Action, Actor, Target, decide, item_actions, transition

ROLES = ["support", "qa", "developer", "product_manager", "cto", "admin"]
ME = 7
OTHER = 8

# capability → roles allowed (no triage-lead designation involved)
EXPECTED = {
    Action.submit_support_report: {"support", "admin"},
    Action.create_item: {"qa", "developer", "product_manager", "cto", "admin"},
    Action.comment_internal: {"qa", "developer", "product_manager", "cto", "admin"},
    Action.report_recurrence: set(ROLES),
    Action.triage: {"qa", "developer", "product_manager", "cto", "admin"},
    transition("in_progress"): {"qa", "developer", "product_manager", "cto", "admin"},
    transition("done"): {"qa", "developer", "product_manager", "cto", "admin"},
    Action.flag_tech_debt: {"qa", "developer", "product_manager", "cto", "admin"},
    Action.manage_backlog: {"product_manager", "cto", "admin"},
    Action.manage_releases: {"product_manager", "cto", "admin"},
    Action.view_team_overview: {"cto", "admin"},
    Action.go_nogo: {"product_manager", "cto", "admin"},
    Action.manage_templates: {"cto", "admin"},
    Action.manage_users: {"cto", "admin"},
    Action.manage_projects: {"cto", "admin"},
    Action.manage_search: {"cto", "admin"},
    Action.flag_release_blocker: {"qa", "product_manager", "cto", "admin"},
    Action.reject: {"qa", "developer", "product_manager", "cto", "admin"},
    Action.mark_production: {"qa", "developer", "product_manager", "cto", "admin"},
    Action.view_reports: {"qa", "developer", "product_manager", "cto", "admin"},
}


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("action", list(EXPECTED), ids=lambda a: getattr(a, "value", a))
def test_matrix_row(action, role):
    target = Target(project_id=1, triage_lead_id=OTHER)
    assert decide(Actor(ME, role), action, target).ok == (role in EXPECTED[action])


@pytest.mark.parametrize("role", ROLES)
def test_own_queue_is_every_tech_role_anyone_elses_is_cto_admin(role):
    tech = role != "support"
    for action in (Action.view_queue, Action.reorder_queue, Action.pin):
        assert decide(Actor(ME, role), action, Target(queue_owner_id=ME)).ok == tech
        assert decide(Actor(ME, role), action, Target(queue_owner_id=OTHER)).ok == (
            role in {"cto", "admin"}
        )


def test_developer_manages_releases_only_as_that_projects_triage_lead():
    dev = Actor(ME, "developer")
    assert decide(dev, Action.manage_releases, Target(project_id=1, triage_lead_id=ME)).ok
    denied = decide(dev, Action.manage_releases, Target(project_id=2, triage_lead_id=OTHER))
    assert not denied.ok and denied.code == "not_triage_lead" and not denied.hidden
    # QA isn't lifted by the lead designation for manage_* (footnote ² is Dev-only).
    assert not decide(Actor(ME, "qa"), Action.manage_backlog, Target(triage_lead_id=ME)).ok


@pytest.mark.parametrize("role", ["developer", "cto"])
def test_flags_include_the_projects_triage_lead(role):
    lead_target = Target(item_id=1, project_id=1, triage_lead_id=ME)
    assert decide(Actor(ME, role), Action.flag_release_blocker, lead_target).ok


def test_support_sees_only_support_sourced_items_and_learns_nothing_else():
    support = Actor(ME, "support")
    internal = decide(support, Action.view_item, Target(item_id=1, source=None))
    assert not internal.ok and internal.not_found and internal.hidden
    # Every item action on an invisible item is a not-found, never a 403.
    assert decide(support, Action.comment_public, Target(item_id=1)).not_found
    assert decide(support, transition("done"), Target(item_id=1)).not_found
    assert decide(support, Action.view_item, Target(item_id=1, source="support")).ok
    assert decide(support, Action.comment_public, Target(item_id=1, source="support")).ok


def test_support_denials_are_hidden_tech_denials_are_not():
    assert decide(Actor(ME, "support"), Action.create_item).hidden
    assert not decide(Actor(ME, "qa"), Action.go_nogo).hidden


@pytest.mark.parametrize("role", ROLES)
def test_only_tech_roles_are_assignable(role):
    d = decide(Actor(ME, "admin"), Action.assign, Target(item_id=1, assignee_role=role))
    assert d.ok == (role != "support")
    if role == "support":
        assert d.code == "not_assignable"
    assert policy.is_assignable(role) == (role != "support")


def test_verifying_your_own_fix_is_not_refused():
    """AC-27 was removed by the 2026-09-22 product decision; Policy must not reinstate it."""
    target = Target(item_id=1, item_type="bug", status="in_review", assignee_id=ME)
    assert decide(Actor(ME, "developer"), transition("done"), target).ok


def test_item_actions_builds_allowed_and_blocked_lists():
    dev = Actor(ME, "developer")
    target = Target(
        item_id=1, item_type="bug", status="todo", project_id=1, triage_lead_id=OTHER,
    )
    allowed, blocked = item_actions(dev, target, ["in_progress", "done"])
    assert "comment_internal" in allowed
    assert "transition:done" in allowed
    blocked_by_action = {b["action"]: b for b in blocked}
    assert blocked_by_action["flag_release_blocker"]["code"] == "not_triage_lead"
    assert blocked_by_action["flag_release_blocker"]["detail"]
    # reject exists only on delivered or Done work — hidden, not blocked, elsewhere.
    assert "reject" not in allowed and "reject" not in blocked_by_action


@pytest.mark.parametrize("status", ["to_review", "in_review", "verified", "done"])
def test_reject_on_delivered_or_done_work(status):
    item = Target(item_id=1, item_type="task", status=status)
    for role in ("qa", "developer", "product_manager", "cto", "admin"):
        assert decide(Actor(ME, role), Action.reject, item).ok
    support = decide(Actor(ME, "support"), Action.reject, Target(
        item_id=1, item_type="bug", status=status, source="support",
    ))
    # BR-71: Support rejects only from To review / In review, and only what it filed.
    assert support.ok == (status in ("to_review", "in_review"))
    if not support.ok:
        assert support.hidden
    internal = decide(Actor(ME, "support"), Action.reject, Target(
        item_id=1, item_type="bug", status=status, source="internal",
        subscriber_ids=frozenset({ME}),
    ))
    assert not internal.ok and internal.hidden


@pytest.mark.parametrize("status", ["todo", "rejected", "in_progress", "blocked", "cancelled"])
def test_reject_hidden_elsewhere(status):
    d = decide(Actor(ME, "qa"), Action.reject, Target(item_id=1, status=status))
    assert not d.ok and d.code == "not_rejectable" and d.hidden


def test_item_actions_hide_tech_controls_from_support():
    support = Actor(ME, "support")
    target = Target(item_id=1, item_type="bug", source="support")
    allowed, blocked = item_actions(support, target, ["in_progress"])
    assert set(allowed) == {"comment_public", "report_recurrence"}
    assert blocked == []
    # Problem is back appears only on a Done item (slice 20).
    done = Target(item_id=1, item_type="bug", status="done", source="support")
    assert "request_return" in item_actions(support, done, [])[0]


def test_support_can_verify_and_close_out_what_it_filed():
    """BR-71 — Verified from To review / In review; Done only in the Stream (slice 20)."""
    support = Actor(ME, "support")
    item = Target(item_id=1, item_type="bug", status="in_review", source="support",
                  container_kind="stream")
    assert decide(support, transition("done"), item).ok
    assert decide(support, transition("verified"), item).ok
    allowed, _ = item_actions(support, item, ["verified", "done", "in_progress"])
    assert {"transition:done", "transition:verified"} <= set(allowed)
    assert "transition:in_progress" not in allowed
    # Not in a release (Done is at ship), and only from To review / In review.
    release = Target(item_id=1, status="in_review", source="support", container_kind="release")
    assert not decide(support, transition("done"), release).ok
    for status in ("todo", "in_progress", "blocked", "verified"):
        d = decide(support, transition("done"), Target(
            item_id=1, status=status, source="support", container_kind="stream"))
        assert not d.ok and d.hidden
    assert decide(support, transition("done"), Target(item_id=1, status="in_review")).not_found


def test_unknown_action_is_denied():
    assert decide(Actor(ME, "admin"), "launch_rockets").code == "unknown_action"


@pytest.mark.parametrize("status", ["todo", "in_review", "done"])
def test_mark_production_is_hidden_unless_the_item_is_verified(status):
    d = decide(Actor(ME, "qa"), Action.mark_production, Target(item_id=1, status=status))
    assert not d.ok and d.code == "not_verified_in_stream" and d.hidden


def test_mark_production_is_for_verified_stream_items_only():
    verified = Target(item_id=1, status="verified", container_kind="stream")
    assert decide(Actor(ME, "developer"), Action.mark_production, verified).ok
    in_release = Target(item_id=1, status="verified", container_kind="release")
    assert not decide(Actor(ME, "developer"), Action.mark_production, in_release).ok
    support = decide(Actor(ME, "support"), Action.mark_production, Target(
        item_id=1, status="verified", container_kind="stream", source="support",
    ))
    assert not support.ok and support.hidden
