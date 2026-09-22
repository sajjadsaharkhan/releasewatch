"""Slice 03 (docs/phase-2/03-tasks-and-placement.md): tasks, hotfix placement,
project kinds.

Bug status movement stays unrestricted (02's later decision, unchanged by
this slice). Tasks are new here and follow the gated table in the spec —
see ``app/workflow.py``'s ``_TASK_STATIC_TARGETS``. Table-driven, mirroring
02's pattern: one test per allowed row, plus the nearest disallowed target.
"""

import pytest
from sqlalchemy import text

from app.db.session import get_engine


async def _new_task(factories, project_id, **overrides):
    payload = {"priority": 2, **overrides}
    return await factories.issue(project_id=project_id, type="task", **payload)


async def _task_in(factories, project_id, target_status, **overrides):
    """Create a task and drive it to ``target_status`` via /transition."""
    task = await _new_task(factories, project_id, **overrides)
    admin = factories.admin_client
    path = {
        "todo": [],
        "in_progress": ["in_progress"],
        "in_review": ["in_progress", "in_review"],
        "done": ["in_progress", "in_review", "done"],
        "blocked": ["in_progress", "blocked"],
    }[target_status]
    for step in path:
        resp = await admin.post(f"/issues/{task.id}/transition", json={"to": step})
        assert resp.status_code == 200, resp.text
    return task


@pytest.fixture
async def rig(factories):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    return {"project": project, "release": release}


# ── Creation: type-specific initial status (FR-05, BR-11, BR-12) ────────────


@pytest.mark.asyncio
async def test_task_starts_in_todo_and_has_task_key(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    assert task.status == "todo"
    assert task.type == "task"
    assert task.key.startswith("TASK-")


@pytest.mark.asyncio
async def test_bug_still_starts_in_new_and_has_bug_key(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["release"].id)
    assert bug.status == "new"
    assert bug.type == "bug"
    assert bug.key.startswith("BUG-")


# ── Task workflow table ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_todo_to_in_progress_allowed(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": "in_progress"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_task_todo_to_done_directly_refused(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.post(f"/issues/{task.id}/transition", json={"to": "done"})
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "invalid_transition"
    assert "in_progress" in body["allowed"]
    assert "done" not in body["allowed"]


@pytest.mark.asyncio
async def test_task_in_progress_to_in_review_allowed(factories, rig):
    task = await _task_in(factories, rig["project"].id, "in_progress")
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": "in_review"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_review"


@pytest.mark.asyncio
async def test_task_in_progress_to_done_allowed(factories, rig):
    task = await _task_in(factories, rig["project"].id, "in_progress")
    resp = await factories.admin_client.post(f"/issues/{task.id}/transition", json={"to": "done"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


@pytest.mark.asyncio
async def test_task_in_review_to_done_allowed(factories, rig):
    task = await _task_in(factories, rig["project"].id, "in_review")
    resp = await factories.admin_client.post(f"/issues/{task.id}/transition", json={"to": "done"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


@pytest.mark.asyncio
async def test_task_in_review_to_in_progress_allowed(factories, rig):
    task = await _task_in(factories, rig["project"].id, "in_review")
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": "in_progress"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
@pytest.mark.parametrize("from_status", ["todo", "in_progress", "in_review"])
async def test_task_can_be_blocked_from(factories, rig, from_status):
    task = await _task_in(factories, rig["project"].id, from_status)
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": "blocked"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "blocked"
    assert body["blocked_from_status"] == from_status


@pytest.mark.asyncio
async def test_task_unblock_returns_to_blocked_from_status(factories, rig):
    task = await _task_in(factories, rig["project"].id, "in_progress")
    admin = factories.admin_client
    await admin.post(f"/issues/{task.id}/transition", json={"to": "blocked"})
    resp = await admin.post(f"/issues/{task.id}/transition", json={"to": "in_progress"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["blocked_from_status"] is None


@pytest.mark.asyncio
async def test_task_done_is_terminal(factories, rig):
    task = await _task_in(factories, rig["project"].id, "done")
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": "in_progress"}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_transition"


@pytest.mark.asyncio
async def test_task_never_offered_new_or_needs_info(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.get(f"/issues/{task.id}")
    allowed = resp.json()["allowed_transitions"]
    assert "new" not in allowed
    assert "needs_info" not in allowed


@pytest.mark.asyncio
async def test_task_transition_to_new_refused(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.post(f"/issues/{task.id}/transition", json={"to": "new"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_transition"


# ── Cancel reasons: task-only vs. bug-only (BR-13) ───────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("from_status", ["todo", "in_progress", "in_review", "blocked"])
async def test_task_cancel_with_no_longer_needed_succeeds(factories, rig, from_status):
    task = await _task_in(factories, rig["project"].id, from_status)
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition",
        json={"to": "cancelled", "cancel_reason": "no_longer_needed"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "no_longer_needed"


@pytest.mark.asyncio
async def test_task_cancel_without_reason_refused(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": "cancelled"}
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_cancel_reason"


@pytest.mark.asyncio
async def test_task_cancel_with_bug_reason_refused(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition",
        json={"to": "cancelled", "cancel_reason": "wont_fix"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_cancel_reason"


@pytest.mark.asyncio
async def test_bug_cancel_with_no_longer_needed_refused(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["release"].id)
    resp = await factories.admin_client.post(
        f"/issues/{bug.id}/transition",
        json={"to": "cancelled", "cancel_reason": "no_longer_needed"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_cancel_reason"


@pytest.mark.asyncio
async def test_bug_cancel_with_bug_reason_still_succeeds(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["release"].id)
    resp = await factories.admin_client.post(
        f"/issues/{bug.id}/transition",
        json={"to": "cancelled", "cancel_reason": "wont_fix"},
    )
    assert resp.status_code == 200
    assert resp.json()["cancel_reason"] == "wont_fix"


# ── IssueCreate validation (422 field errors, BR-07/BR-08/BR-09) ────────────


@pytest.mark.asyncio
async def test_task_requires_priority(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "no priority", "type": "task", "project_id": rig["project"].id,
    })
    assert resp.status_code == 422
    # Field-level error, so a form can highlight the priority control (spec:
    # "Validation, all 422 with a field error").
    locs = [tuple(e["loc"]) for e in resp.json()["detail"]]
    assert ("body", "priority") in locs


@pytest.mark.asyncio
async def test_task_cannot_have_severity(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "has severity", "type": "task", "project_id": rig["project"].id,
        "priority": 2, "severity": "major",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_bug_cannot_have_priority(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "has priority", "type": "bug", "project_id": rig["project"].id,
        "release_id": rig["release"].id, "priority": 2,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_task_cannot_be_release_blocker(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "blocker task", "type": "task", "project_id": rig["project"].id,
        "priority": 2, "is_release_blocker": True,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_task_cannot_have_curl_command(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "curl task", "type": "task", "project_id": rig["project"].id,
        "priority": 2, "curl_command": "curl https://example.com",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_task_cannot_have_environment_name(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "env task", "type": "task", "project_id": rig["project"].id,
        "priority": 2, "environment_name": "staging",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_task_cannot_have_reproduction_steps(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "repro task", "type": "task", "project_id": rig["project"].id,
        "priority": 2,
        "reproduction_steps": [{"step_order": 1, "description": "do a thing"}],
    })
    assert resp.status_code == 422


# ── Placement: release optionality + project kind (BR-02, BR-03, BR-26) ─────


@pytest.mark.asyncio
async def test_bug_with_no_release_is_a_hotfix(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, release_id=None)
    assert bug.release_id is None
    assert bug.type == "bug"


@pytest.mark.asyncio
async def test_release_on_non_product_project_refused(factories):
    project = await factories.project(kind="internal")
    resp = await factories.admin_client.post("/issues", json={
        "title": "release on internal project", "type": "bug", "project_id": project.id,
        "release_id": 999999,
    })
    assert resp.status_code == 409
    assert resp.json()["code"] == "releases_not_allowed"


@pytest.mark.asyncio
async def test_release_from_different_project_refused(factories, rig):
    other_project = await factories.project()
    resp = await factories.admin_client.post("/issues", json={
        "title": "cross-project release", "type": "bug", "project_id": other_project.id,
        "release_id": rig["release"].id,
    })
    assert resp.status_code == 409
    assert resp.json()["code"] == "release_project_mismatch"


@pytest.mark.asyncio
async def test_task_filed_against_general_project(factories):
    project = await factories.project(kind="general")
    task = await _new_task(factories, project.id)
    assert task.status == "todo"
    assert task.release_id is None


# ── type is immutable once created (BR-07) ───────────────────────────────────


@pytest.mark.asyncio
async def test_type_immutable_on_patch(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.patch(f"/issues/{task.id}", json={"type": "bug"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "type_immutable"


# ── Project kind change refused while it has releases (BR-02) ───────────────


@pytest.mark.asyncio
async def test_project_kind_change_refused_with_releases(factories, rig):
    resp = await factories.admin_client.patch(
        f"/projects/id/{rig['project'].id}", json={"kind": "internal"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "project_has_releases"


@pytest.mark.asyncio
async def test_project_kind_change_allowed_without_releases(factories):
    project = await factories.project()
    resp = await factories.admin_client.patch(
        f"/projects/id/{project.id}", json={"kind": "internal"},
    )
    assert resp.status_code == 200
    assert resp.json()["kind"] == "internal"


# ── GET /issues filters ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_filter_by_type(factories, rig):
    await _new_task(factories, rig["project"].id)
    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["release"].id)

    resp = await factories.admin_client.get("/issues", params={"type": "bug"})
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert bug.id in ids
    assert all(i["type"] == "bug" for i in resp.json()["items"])


@pytest.mark.asyncio
async def test_filter_by_has_release(factories, rig):
    hotfix = await factories.issue(project_id=rig["project"].id, release_id=None)
    resp = await factories.admin_client.get("/issues", params={"has_release": "false"})
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert hotfix.id in ids
    assert all(i["release_id"] is None for i in resp.json()["items"])


@pytest.mark.asyncio
async def test_filter_by_is_urgent(factories, rig):
    urgent = await factories.issue(
        project_id=rig["project"].id, release_id=rig["release"].id, is_urgent=True,
    )
    resp = await factories.admin_client.get("/issues", params={"is_urgent": "true"})
    assert resp.status_code == 200
    ids = [i["id"] for i in resp.json()["items"]]
    assert urgent.id in ids


@pytest.mark.asyncio
async def test_filter_by_project_kind(factories, rig):
    internal_project = await factories.project(kind="internal")
    internal_task = await _new_task(factories, internal_project.id)
    product_bug = await factories.issue(
        project_id=rig["project"].id, release_id=rig["release"].id,
    )

    resp = await factories.admin_client.get("/issues", params={"project_kind": "internal"})
    assert resp.status_code == 200
    body = resp.json()
    ids = [i["id"] for i in body["items"]]
    assert internal_task.id in ids
    assert product_bug.id not in ids


# ── AC-24: urgent clears on done; verifying a hotfix closes it (FR-21) ──────


@pytest.mark.asyncio
async def test_ac_24_urgent_hotfix_verified_clears_urgent(factories, client_for, rig):
    developer = await factories.user(role="developer")
    admin = factories.admin_client

    bug = await factories.issue(
        project_id=rig["project"].id, release_id=None, is_urgent=True,
    )
    assert bug.is_urgent is True
    assert bug.release_id is None

    resp = await admin.post(
        f"/issues/{bug.id}/triage", json={"assignee_id": developer.id, "severity": "major"},
    )
    assert resp.status_code == 200
    assert resp.json()["is_urgent"] is True

    dev_client = await client_for(developer)
    resp = await dev_client.post(f"/issues/{bug.id}/transition", json={"to": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["is_urgent"] is True

    resp = await dev_client.post(f"/issues/{bug.id}/fix", json={"mr_url": None})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_review"
    assert resp.json()["is_urgent"] is True

    resp = await admin.post(f"/issues/{bug.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["is_urgent"] is False

    timeline = await admin.get(f"/issues/{bug.id}/timeline")
    assert timeline.status_code == 200
    event_types = [e["event_type"] for e in timeline.json()["items"]]
    assert "urgent_flagged" in event_types
    assert "urgent_cleared" in event_types


@pytest.mark.asyncio
async def test_setting_urgent_via_patch_notifies_assignee(factories, client_for, rig):
    developer = await factories.user(role="developer")
    bug = await factories.issue(
        project_id=rig["project"].id, release_id=rig["release"].id, assignee_id=developer.id,
    )
    resp = await factories.admin_client.patch(f"/issues/{bug.id}", json={"is_urgent": True})
    assert resp.status_code == 200
    assert resp.json()["is_urgent"] is True

    dev_client = await client_for(developer)
    inbox_resp = await dev_client.get("/inbox")
    assert inbox_resp.status_code == 200
    types = [item["type"] for item in inbox_resp.json()["items"]]
    assert "urgent" in types


# ── Deleting a release nulls release_id instead of deleting the issue ───────
# No hard-delete-release endpoint exists (DELETE /releases/{id} is a soft
# delete) — the ON DELETE SET NULL FK is only observable at the DB level.


@pytest.mark.asyncio
async def test_hard_deleting_release_nulls_issue_release_id(factories, db_session, rig):
    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["release"].id)

    await db_session.rollback()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM releases WHERE id = :id"), {"id": rig["release"].id})

    resp = await factories.admin_client.get(f"/issues/{bug.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == bug.id
    assert body["release_id"] is None
