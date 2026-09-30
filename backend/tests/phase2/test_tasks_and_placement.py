"""Slice 03 (docs/phase-2/03-tasks-and-placement.md): tasks, hotfix placement,
containers (08a).

Status movement is unrestricted for both types (the 2026-09-22 decision for
bugs, extended to tasks on 2026-09-23): a task can move from any of its
statuses to any other. ``new`` and ``needs_info`` stay bug-only (BR-10).
"""

import pytest
from sqlalchemy import text

from app.db.session import get_engine


async def _new_task(factories, project_id, **overrides):
    return await factories.issue(project_id=project_id, type="task", **overrides)


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


# ── Task workflow: free movement between task statuses ───────────────────────

TASK_STATUSES = ["todo", "in_progress", "to_review", "in_review", "done", "blocked", "cancelled"]


@pytest.mark.asyncio
async def test_task_todo_to_in_progress_allowed(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": "in_progress"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"


@pytest.mark.asyncio
async def test_task_todo_to_done_directly_allowed(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.post(f"/issues/{task.id}/transition", json={"to": "done"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


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
@pytest.mark.parametrize("from_status", ["todo", "in_progress", "in_review", "done", "blocked"])
async def test_task_offers_every_other_task_status(factories, rig, from_status):
    task = await _task_in(factories, rig["project"].id, from_status)
    resp = await factories.admin_client.get(f"/issues/{task.id}")
    allowed = set(resp.json()["allowed_transitions"])
    # Rejected is never offered: only Reject enters it (09a).
    assert allowed == set(TASK_STATUSES) - {from_status, "rejected"}


@pytest.mark.asyncio
@pytest.mark.parametrize("to_status", ["todo", "in_progress", "in_review", "blocked", "cancelled"])
async def test_task_done_can_move_to_any_task_status(factories, rig, to_status):
    task = await _task_in(factories, rig["project"].id, "done")
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": to_status}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == to_status


@pytest.mark.asyncio
async def test_task_cancelled_can_be_restored(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    admin = factories.admin_client
    await admin.post(
        f"/issues/{task.id}/transition",
        json={"to": "cancelled", "cancel_reason": "no_longer_needed"},
    )
    resp = await admin.post(f"/issues/{task.id}/transition", json={"to": "todo"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "todo"
    assert body["cancel_reason"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("to_status", ["todo", "blocked", "in_review"])
async def test_task_leaving_done_clears_completion(factories, rig, to_status):
    task = await _task_in(factories, rig["project"].id, "done")
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": to_status}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["completed_at"] is None
    assert body["verified_at"] is None


@pytest.mark.asyncio
async def test_task_unblock_can_go_anywhere(factories, rig):
    task = await _task_in(factories, rig["project"].id, "in_progress")
    admin = factories.admin_client
    await admin.post(f"/issues/{task.id}/transition", json={"to": "blocked"})
    resp = await admin.post(f"/issues/{task.id}/transition", json={"to": "done"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["blocked_from_status"] is None


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
async def test_task_cancel_without_reason_allowed(factories, rig):
    """Like a bug, a task may be cancelled from the status control with no reason."""
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": "cancelled"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] is None


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
async def test_task_cannot_be_release_blocker(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "blocker task", "type": "task", "project_id": rig["project"].id,
        "is_release_blocker": True,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_task_cannot_have_curl_command(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "curl task", "type": "task", "project_id": rig["project"].id,
        "curl_command": "curl https://example.com",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_task_cannot_have_environment_name(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "env task", "type": "task", "project_id": rig["project"].id,
        "environment_name": "staging",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_task_cannot_have_reproduction_steps(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "repro task", "type": "task", "project_id": rig["project"].id,
        "reproduction_steps": [{"step_order": 1, "description": "do a thing"}],
    })
    assert resp.status_code == 422


# ── Placement: backlog, Stream, or a Release (08a) ──────────────────────────


@pytest.mark.asyncio
async def test_bug_with_no_container_is_in_triage_with_no_container(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, release_id=None)
    assert bug.release_id is None
    assert bug.container_kind is None
    assert bug.type == "bug"


@pytest.mark.asyncio
async def test_unknown_container_refused(factories, rig):
    resp = await factories.admin_client.post("/issues", json={
        "title": "unknown container", "type": "bug", "project_id": rig["project"].id,
        "release_id": 999999,
    })
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_release_from_different_project_refused(factories, rig):
    other_project = await factories.project()
    resp = await factories.admin_client.post("/issues", json={
        "title": "cross-project release", "type": "bug", "project_id": other_project.id,
        "release_id": rig["release"].id,
    })
    assert resp.status_code == 409
    assert resp.json()["code"] == "release_project_mismatch"


# ── type is immutable once created (BR-07) ───────────────────────────────────


@pytest.mark.asyncio
async def test_type_immutable_on_patch(factories, rig):
    task = await _new_task(factories, rig["project"].id)
    resp = await factories.admin_client.patch(f"/issues/{task.id}", json={"type": "bug"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "type_immutable"


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
async def test_filter_by_container(factories, rig):
    project = rig["project"]
    stream_id = (await factories.admin_client.get(f"/projects/id/{project.id}")).json()["stream_id"]
    in_backlog = await _new_task(factories, project.id)
    in_stream = await _new_task(factories, project.id, release_id=stream_id)
    in_release = await _new_task(factories, project.id, release_id=rig["release"].id)

    async def ids(container):
        resp = await factories.admin_client.get(
            "/issues", params={"container": container, "project_id": project.id},
        )
        assert resp.status_code == 200
        return {i["id"] for i in resp.json()["items"]}

    assert await ids("backlog") == {in_backlog.id}
    assert await ids("stream") == {in_stream.id}
    assert await ids(str(rig["release"].id)) == {in_release.id}


@pytest.mark.asyncio
async def test_old_placement_filters_are_gone(factories, rig):
    resp = await factories.admin_client.get("/issues", params={"container": "hotfix"})
    assert resp.status_code == 422


# ── AC-24: a bug in the Stream reaches Done when verified (FR-21, v3) ──────


@pytest.mark.asyncio
async def test_ac_24_stream_bug_verified_is_done(factories, client_for, rig):
    developer = await factories.user(role="developer")
    admin = factories.admin_client
    stream_id = (await admin.get(f"/projects/id/{rig['project'].id}")).json()["stream_id"]

    bug = await factories.issue(project_id=rig["project"].id, release_id=None)
    resp = await admin.post(f"/issues/{bug.id}/triage", json={
        "outcome": "accept", "assignee_id": developer.id, "priority": "high",
        "release_id": stream_id,
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "todo"
    assert resp.json()["release_id"] == stream_id
    assert resp.json()["container_kind"] == "stream"

    dev_client = await client_for(developer)
    resp = await dev_client.post(f"/issues/{bug.id}/transition", json={"to": "in_progress"})
    assert resp.status_code == 200

    resp = await dev_client.post(f"/issues/{bug.id}/fix", json={"mr_url": None})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_review"

    resp = await admin.post(f"/issues/{bug.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["release_id"] == stream_id


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
