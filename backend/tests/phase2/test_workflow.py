"""Workflow — status movement is unrestricted, tested only through the API.

Per product decision (2026-09-22, superseding the original slice-02 spec's
Workflow gating): a bug can move from any status to any other status via
POST /issues/{id}/transition (and PATCH), with no reason required, no
self-verification block, and no release gate on the regression action. See
``app/workflow.py``. The dedicated action endpoints (/triage, /fix,
/verify, /reopen) keep their own specific
preconditions — those aren't part of Workflow and weren't loosened.
"""

import pytest

from app.db.models.issue import IssueStatus


async def _new_bug(factories, release_id, **overrides):
    return await factories.issue(release_id=release_id, **overrides)


async def _todo_bug(factories, client_for, release_id, developer):
    """A bug triaged to todo, assigned to ``developer``."""
    issue = await _new_bug(factories, release_id)
    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/triage",
        json={"outcome": "accept", "assignee_id": developer.id, "priority": "high"},
    )
    assert resp.status_code == 200
    return issue


async def _in_progress_bug(factories, client_for, release_id, developer):
    issue = await _todo_bug(factories, client_for, release_id, developer)
    dev_client = await client_for(developer)
    resp = await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    assert resp.status_code == 200
    return issue


async def _in_review_bug(factories, client_for, release_id, developer):
    issue = await _in_progress_bug(factories, client_for, release_id, developer)
    dev_client = await client_for(developer)
    resp = await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})
    assert resp.status_code == 200
    return issue


async def _done_bug(factories, client_for, release_id, developer, verifier_client):
    issue = await _in_review_bug(factories, client_for, release_id, developer)
    resp = await verifier_client.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    return issue


@pytest.fixture
async def rig(factories):
    developer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    return {"developer": developer, "project": project, "release": release}


# ── allowed_transitions reflects every other status ─────────────────────────


@pytest.mark.asyncio
async def test_allowed_transitions_includes_every_other_status(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client
    resp = await admin.get(f"/issues/{issue.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["allowed_transitions"]) == {s.value for s in IssueStatus} - {"new"}
    assert body["blocked_transitions"] == []


# ── any status reaches any other status directly ────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "to", ["todo", "in_progress", "in_review", "done", "blocked", "cancelled", "needs_info"],
)
async def test_new_bug_can_move_directly_to_any_status(factories, rig, to):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": to})
    assert resp.status_code == 200
    assert resp.json()["status"] == to


@pytest.mark.asyncio
async def test_done_bug_can_move_back_to_new(factories, client_for, rig):
    admin = factories.admin_client
    issue = await _done_bug(factories, client_for, rig["release"].id, rig["developer"], admin)
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "new"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "new"


@pytest.mark.asyncio
async def test_blocked_bug_can_move_directly_to_done(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    await admin.post(f"/issues/{issue.id}/transition", json={"to": "blocked"})
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "done"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


# ── cancel no longer requires a reason ───────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_without_reason_succeeds(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "cancelled"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] is None
    assert body["cancelled_at"] is not None


@pytest.mark.asyncio
async def test_cancel_with_reason_still_records_it(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/transition",
        json={"to": "cancelled", "cancel_reason": "wont_fix"},
    )
    assert resp.status_code == 200
    assert resp.json()["cancel_reason"] == "wont_fix"


# ── AC-27 (self-verification) is no longer enforced ──────────────────────────


@pytest.mark.asyncio
async def test_reviewer_can_verify_own_fix(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    dev_client = await client_for(rig["developer"])
    await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})

    resp = await dev_client.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


# ── BR-24 (regression release gate) is no longer enforced ───────────────────


@pytest.mark.asyncio
async def test_regression_action_works_without_a_release(factories, client_for, rig):
    """The regression action is callable from any status, release or not."""
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client

    resp = await admin.post(f"/issues/{issue.id}/regression")
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    history = await admin.get(f"/issues/{issue.id}/regressions")
    assert history.status_code == 200


@pytest.mark.asyncio
async def test_regression_action_on_shipped_release_still_succeeds(factories, client_for, rig):
    admin = factories.admin_client
    issue = await _done_bug(factories, client_for, rig["release"].id, rig["developer"], admin)
    await admin.patch(f"/releases/{rig['release'].id}", json={"status": "released"})

    resp = await admin.post(f"/issues/{issue.id}/regression")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["is_regression"] is True
    assert body["regression_count"] == 1


# ── reopen keeps its own precondition (unaffected by Workflow) ──────────────


@pytest.mark.asyncio
async def test_reopen_still_requires_done(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/reopen")
    assert resp.status_code == 409
    assert resp.json()["code"] == "done_is_final"


# ── PATCH obeys the same (unrestricted) rules ────────────────────────────────


@pytest.mark.asyncio
async def test_patch_status_is_also_unrestricted(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client
    resp = await admin.patch(f"/issues/{issue.id}", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
