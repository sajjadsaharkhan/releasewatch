"""Workflow — status movement is unrestricted, tested only through the API.

Per product decision (2026-09-22, superseding the original slice-02 spec's
Workflow gating): a bug can move from any status to any other status via
POST /issues/{id}/transition (and PATCH), with no reason required, no
self-verification block, and no release gate on the regression action. See
``app/workflow.py``. The dedicated action endpoints (/triage, /fix,
/verify, /reopen → /returns) keep their own specific
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


async def _verified_bug(factories, client_for, release_id, developer, verifier_client):
    """QA's pass: Verified (not Done — Done means on production, v3.1)."""
    issue = await _in_review_bug(factories, client_for, release_id, developer)
    resp = await verifier_client.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "verified"
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
    # Rejected is never offered: only Reject enters it (09a). A release item
    # never lists Done either — only ship writes it (the Done gate, BR-68).
    assert set(body["allowed_transitions"]) == (
        {s.value for s in IssueStatus} - {"new", "rejected", "done"}
    )
    # Only the Done gate is reported as blocked (BR-68).
    assert [(b["to"], b["code"]) for b in body["blocked_transitions"]] == [("done", "done_at_ship")]


# ── any status reaches any other status directly ────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "to", ["todo", "in_progress", "in_review", "verified", "blocked", "cancelled", "needs_info"],
)
async def test_new_bug_can_move_directly_to_any_status(factories, rig, to):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": to})
    assert resp.status_code == 200
    assert resp.json()["status"] == to


@pytest.mark.asyncio
async def test_new_release_bug_cannot_move_to_done(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    resp = await factories.admin_client.post(f"/issues/{issue.id}/transition", json={"to": "done"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "done_at_ship"


@pytest.mark.asyncio
async def test_verified_bug_can_move_back_to_new(factories, client_for, rig):
    admin = factories.admin_client
    issue = await _verified_bug(factories, client_for, rig["release"].id, rig["developer"], admin)
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "new"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "new"


@pytest.mark.asyncio
async def test_blocked_bug_can_move_directly_to_verified(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    await admin.post(f"/issues/{issue.id}/transition", json={"to": "blocked"})
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "verified"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "verified"


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
    assert resp.json()["status"] == "verified"


# ── 08a: the regression action is gone; returns replace it ─────────────────


@pytest.mark.asyncio
async def test_regression_endpoint_is_removed(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    resp = await factories.admin_client.post(f"/issues/{issue.id}/regression")
    assert resp.status_code in (404, 405)


@pytest.mark.asyncio
async def test_reopen_maps_to_returns_and_still_requires_done(factories, client_for, rig):
    admin = factories.admin_client
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    resp = await admin.post(f"/issues/{issue.id}/reopen", json={"comment": "Back"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "not_done"

    verified = await _verified_bug(
        factories, client_for, rig["release"].id, rig["developer"], admin,
    )
    resp = await admin.post(f"/issues/{verified.id}/reopen", json={"comment": "Back"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "not_done"

    # Shipping makes it Done — on production — and reopen sends it back as an escape.
    await factories.set_release_status(rig["release"].id, "released")
    resp = await admin.post(f"/issues/{verified.id}/reopen", json={"comment": "Back"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["reject_reason"] == "production"


# ── PATCH obeys the same (unrestricted) rules ────────────────────────────────


@pytest.mark.asyncio
async def test_patch_status_is_also_unrestricted(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client
    resp = await admin.patch(f"/issues/{issue.id}", json={"status": "verified"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "verified"
    # …except the Done gate: a release item can't be set to Done by PATCH either.
    resp = await admin.patch(f"/issues/{issue.id}", json={"status": "done"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "done_at_ship"
