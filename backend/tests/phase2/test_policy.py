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

ROLES = ["support", "qa", "developer", "pm", "cto", "admin"]
ME = 7
OTHER = 8

# capability → roles allowed (no triage-lead designation involved)
EXPECTED = {
    Action.submit_support_report: {"support", "admin"},
    Action.create_item: {"qa", "developer", "pm", "cto", "admin"},
    Action.comment_internal: {"qa", "developer", "pm", "cto", "admin"},
    Action.report_recurrence: set(ROLES),
    Action.triage: {"qa", "developer", "pm", "cto", "admin"},
    transition("in_progress"): {"qa", "developer", "pm", "cto", "admin"},
    transition("done"): {"qa", "developer", "pm", "cto", "admin"},
    Action.flag_tech_debt: {"qa", "developer", "pm", "cto", "admin"},
    Action.manage_backlog: {"pm", "cto", "admin"},
    Action.manage_releases: {"pm", "cto", "admin"},
    Action.manage_milestones: {"pm", "cto", "admin"},
    Action.view_team_overview: {"cto", "admin"},
    Action.go_nogo: {"cto", "admin"},
    Action.manage_templates: {"cto", "admin"},
    Action.manage_users: {"admin"},
    Action.manage_projects: {"admin"},
    Action.manage_search: {"admin"},
    Action.flag_release_blocker: {"qa", "pm", "cto", "admin"},
    Action.flag_regression: {"qa", "pm", "admin"},
    Action.view_reports: {"qa", "developer", "pm", "cto", "admin"},
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
    assert decide(Actor(ME, role), Action.flag_regression, lead_target).ok
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
    target = Target(item_id=1, item_type="bug", project_id=1, triage_lead_id=OTHER)
    allowed, blocked = item_actions(dev, target, ["in_progress", "done"])
    assert "comment_internal" in allowed
    assert "transition:done" in allowed
    blocked_by_action = {b["action"]: b for b in blocked}
    assert blocked_by_action["flag_regression"]["code"] == "not_triage_lead"
    assert blocked_by_action["flag_release_blocker"]["detail"]


def test_item_actions_hide_tech_controls_from_support():
    support = Actor(ME, "support")
    target = Target(item_id=1, item_type="bug", source="support")
    allowed, blocked = item_actions(support, target, ["in_progress"])
    assert set(allowed) == {"comment_public", "report_recurrence"}
    assert blocked == []


def test_unknown_action_is_denied():
    assert decide(Actor(ME, "admin"), "launch_rockets").code == "unknown_action"
