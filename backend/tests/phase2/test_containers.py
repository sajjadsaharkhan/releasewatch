"""08a Part 1 — containers: one Stream per project, Releases, and the backlog.

docs/phase-2/08a-release-stream-cycles.md (PRD v3 §8.1, FR-03, FR-18, FR-25,
FR-46, BR-51, BR-54, BR-58; AC-55, AC-58, AC-65).
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.db.session import get_engine


@pytest.fixture
async def rig(factories):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    stream_id = await factories.stream_id(project_id=project.id)
    return {"project": project, "release": release, "stream_id": stream_id}


async def _accepted_bug(factories, rig, *, release_id, **accept):
    bug = await factories.issue(project_id=rig["project"].id)
    resp = await factories.admin_client.post(f"/issues/{bug.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": release_id, **accept,
    })
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _drive(admin, issue_id, *steps):
    for step in steps:
        resp = await admin.post(f"/issues/{issue_id}/transition", json={"to": step})
        assert resp.status_code == 200, resp.text
    return resp.json()


# ── AC-55: every project has one immutable Stream ────────────────────────────


@pytest.mark.asyncio
async def test_ac_55_project_has_one_immutable_stream(factories, rig):
    admin = factories.admin_client
    stream_id = rig["stream_id"]
    assert stream_id is not None

    stream = (await admin.get(f"/releases/{stream_id}")).json()
    assert stream["kind"] == "stream"
    assert stream["status"] is None
    assert stream["project_id"] == rig["project"].id

    for resp in (
        await admin.patch(f"/releases/{stream_id}", json={"version": "Renamed"}),
        await admin.patch(f"/releases/{stream_id}", json={"status": "cancelled"}),
        await admin.delete(f"/releases/{stream_id}"),
        await admin.post(f"/releases/{stream_id}/approve"),
        await admin.post(f"/releases/{stream_id}/block", json={"decision": "blocked"}),
    ):
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "stream_immutable"

    # Still there and unchanged.
    stream = (await admin.get(f"/releases/{stream_id}")).json()
    assert stream["version"] == "Stream"


@pytest.mark.asyncio
async def test_project_create_creates_exactly_one_stream(factories, db_session):
    project = await factories.project()
    await db_session.rollback()
    async with get_engine().begin() as conn:
        count = (await conn.execute(text(
            "SELECT count(*) FROM releases WHERE project_id = :p AND kind = 'stream'"
        ), {"p": project.id})).scalar_one()
    assert count == 1


@pytest.mark.asyncio
async def test_second_stream_insert_fails(factories, db_session):
    project = await factories.project()
    await db_session.rollback()
    with pytest.raises(IntegrityError):
        async with get_engine().begin() as conn:
            await conn.execute(text(
                "INSERT INTO releases (project_id, kind, version, status, go_nogo_status) "
                "VALUES (:p, 'stream', 'Stream', NULL, 'pending')"
            ), {"p": project.id})


@pytest.mark.asyncio
async def test_release_lists_never_include_the_stream(factories, rig):
    admin = factories.admin_client
    listed = (await admin.get("/releases", params={"project_id": rig["project"].id})).json()
    assert [r["id"] for r in listed["releases"]] == [rig["release"].id]

    nested = (await admin.get(f"/projects/{rig['project'].slug}/releases")).json()
    assert [r["id"] for r in nested] == [rig["release"].id]


# ── Release status values (v3 lifecycle) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_new_release_starts_in_planning_with_v3_fields(factories, rig):
    release = rig["release"]
    assert release.kind == "release"
    assert release.status == "planning"
    assert release.code_freeze_date is None
    assert release.released_at is None


@pytest.mark.asyncio
async def test_release_status_controls_use_v3_values(factories, rig):
    admin = factories.admin_client
    rid = rig["release"].id
    for value in ("development", "qa"):
        resp = await admin.patch(f"/releases/{rid}", json={"status": value})
        assert resp.status_code == 200 and resp.json()["status"] == value
    # Released is reached only by shipping (slice 09).
    resp = await admin.patch(f"/releases/{rid}", json={"status": "released"})
    assert resp.status_code == 409 and resp.json()["code"] == "use_ship"
    resp = await admin.post(f"/releases/{rid}/ship", json={"confirm": True})
    assert resp.status_code == 200
    assert resp.json()["released_at"] is not None

    other = (await factories.release(project_id=rig["project"].id)).id
    for old in ("active", "blocked", "archived"):
        resp = await admin.patch(f"/releases/{other}", json={"status": old})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_no_go_keeps_the_release_in_qa(factories, rig):
    admin = factories.admin_client
    rid = rig["release"].id
    await factories.set_release_status(rid, "qa")
    resp = await admin.post(f"/releases/{rid}/block", json={"decision": "blocked", "note": "crash"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "qa"
    assert resp.json()["go_nogo_status"] == "blocked"


@pytest.mark.asyncio
async def test_code_freeze_date_can_be_set(factories, rig):
    resp = await factories.admin_client.patch(
        f"/releases/{rig['release'].id}", json={"code_freeze_date": "2026-10-15"},
    )
    assert resp.status_code == 200
    assert resp.json()["code_freeze_date"] == "2026-10-15"


# ── Placement: create, accept, PATCH, bulk move ───────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("where", ["stream", "release"])
async def test_create_accepts_stream_and_open_release(factories, rig, where):
    target = rig["stream_id"] if where == "stream" else rig["release"].id
    task = await factories.issue(project_id=rig["project"].id, type="task", release_id=target)
    assert task.release_id == target
    assert task.container_kind == where


@pytest.mark.asyncio
@pytest.mark.parametrize("closed", ["released", "cancelled"])
async def test_every_placement_path_refuses_a_closed_release(factories, rig, closed):
    admin = factories.admin_client
    project_id = rig["project"].id
    closed_release = await factories.release(project_id=project_id)
    backlog_task = await factories.issue(project_id=project_id, type="task")
    new_bug = await factories.issue(project_id=project_id)
    await factories.set_release_status(closed_release.id, closed)

    create = await admin.post("/issues", json={
        "title": "into a closed release", "type": "task", "project_id": project_id,
        "release_id": closed_release.id,
    })
    accept = await admin.post(f"/issues/{new_bug.id}/triage", json={
        "outcome": "accept", "priority": "low", "release_id": closed_release.id,
    })
    patch = await admin.patch(f"/issues/{backlog_task.id}", json={"release_id": closed_release.id})
    bulk = await admin.post("/issues/bulk-move", json={
        "issue_ids": [backlog_task.id], "release_id": closed_release.id,
    })
    for resp in (create, accept, patch, bulk):
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "release_closed"


@pytest.mark.asyncio
async def test_every_placement_path_refuses_another_projects_container(factories, rig):
    admin = factories.admin_client
    project_id = rig["project"].id
    other = await factories.project()
    other_stream = await factories.stream_id(project_id=other.id)
    backlog_task = await factories.issue(project_id=project_id, type="task")
    new_bug = await factories.issue(project_id=project_id)

    create = await admin.post("/issues", json={
        "title": "into another project's stream", "type": "task", "project_id": project_id,
        "release_id": other_stream,
    })
    accept = await admin.post(f"/issues/{new_bug.id}/triage", json={
        "outcome": "accept", "priority": "low", "release_id": other_stream,
    })
    patch = await admin.patch(f"/issues/{backlog_task.id}", json={"release_id": other_stream})
    for resp in (create, accept, patch):
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "release_project_mismatch"

    bulk = await admin.post("/issues/bulk-move", json={
        "issue_ids": [backlog_task.id], "release_id": other_stream,
    })
    assert bulk.status_code == 409
    assert bulk.json()["code"] == "bulk_move_failed"


@pytest.mark.asyncio
async def test_accept_into_the_stream(factories, rig):
    body = await _accepted_bug(factories, rig, release_id=rig["stream_id"])
    assert body["release_id"] == rig["stream_id"]
    assert body["container_kind"] == "stream"


@pytest.mark.asyncio
async def test_patch_moves_between_backlog_stream_and_release(factories, rig):
    admin = factories.admin_client
    task = await factories.issue(project_id=rig["project"].id, type="task")
    for target in (rig["stream_id"], rig["release"].id, None, rig["stream_id"]):
        resp = await admin.patch(f"/issues/{task.id}", json={"release_id": target})
        assert resp.status_code == 200, resp.text
        assert resp.json()["release_id"] == target


@pytest.mark.asyncio
@pytest.mark.parametrize("where", ["stream", "release"])
async def test_bulk_move_backlog_items_to_stream_or_release(factories, rig, where):
    target = rig["stream_id"] if where == "stream" else rig["release"].id
    tasks = [await factories.issue(project_id=rig["project"].id, type="task") for _ in range(2)]
    resp = await factories.admin_client.post("/issues/bulk-move", json={
        "issue_ids": [t.id for t in tasks], "release_id": target,
    })
    assert resp.status_code == 200, resp.text
    assert sorted(resp.json()["moved_ids"]) == sorted(t.id for t in tasks)
    assert {i["container_kind"] for i in resp.json()["items"]} == {where}


# ── AC-58: a Done item never changes container ────────────────────────────────


@pytest.mark.asyncio
async def test_ac_58_done_item_cannot_change_container(factories, rig):
    admin = factories.admin_client
    task = await factories.issue(
        project_id=rig["project"].id, type="task", release_id=rig["release"].id,
    )
    await _drive(admin, task.id, "in_progress", "in_review", "done")

    for target in (rig["stream_id"], None):
        resp = await admin.patch(f"/issues/{task.id}", json={"release_id": target})
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "done_item_immobile"

    # Bulk move fails as a whole, the movable item stays where it was.
    movable = await factories.issue(project_id=rig["project"].id, type="task")
    resp = await admin.post("/issues/bulk-move", json={
        "issue_ids": [movable.id, task.id], "release_id": rig["stream_id"],
    })
    assert resp.status_code == 409
    assert resp.json()["code"] == "done_item_immobile"
    assert str(task.id) in resp.json()["errors"]
    assert (await admin.get(f"/issues/{movable.id}")).json()["release_id"] is None
    assert (await admin.get(f"/issues/{task.id}")).json()["release_id"] == rig["release"].id


@pytest.mark.asyncio
async def test_done_item_cannot_move_to_another_project(factories, rig):
    admin = factories.admin_client
    other = await factories.project()
    task = await factories.issue(project_id=rig["project"].id, type="task")
    await _drive(admin, task.id, "in_progress", "in_review", "done")

    resp = await admin.post(f"/issues/{task.id}/move", json={"project_id": other.id})
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "done_item_immobile"
    assert (await admin.get(f"/issues/{task.id}")).json()["project_id"] == rig["project"].id


@pytest.mark.asyncio
async def test_done_item_edits_that_keep_the_container_still_work(factories, rig):
    admin = factories.admin_client
    task = await factories.issue(
        project_id=rig["project"].id, type="task", release_id=rig["stream_id"],
    )
    await _drive(admin, task.id, "in_progress", "in_review", "done")
    resp = await admin.patch(f"/issues/{task.id}", json={
        "title": "renamed", "release_id": rig["stream_id"],
    })
    assert resp.status_code == 200, resp.text


# ── AC-65: the release blocker exists only on a bug in a Release ─────────────


@pytest.mark.asyncio
async def test_ac_65_release_blocker_unavailable_in_stream(factories, rig):
    admin = factories.admin_client
    project_id = rig["project"].id

    resp = await admin.post("/issues", json={
        "title": "blocker in the stream", "type": "bug", "project_id": project_id,
        "release_id": rig["stream_id"], "is_release_blocker": True,
    })
    assert resp.status_code == 409
    assert resp.json()["code"] == "release_blocker_release_only"

    stream_bug = await _accepted_bug(factories, rig, release_id=rig["stream_id"])
    resp = await admin.patch(f"/issues/{stream_bug['id']}", json={"is_release_blocker": True})
    assert resp.status_code == 409
    assert resp.json()["code"] == "release_blocker_release_only"

    backlog_bug = await _accepted_bug(factories, rig, release_id=None)
    resp = await admin.patch(f"/issues/{backlog_bug['id']}", json={"is_release_blocker": True})
    assert resp.status_code == 409
    assert resp.json()["code"] == "release_blocker_release_only"

    release_bug = await _accepted_bug(factories, rig, release_id=rig["release"].id)
    resp = await admin.patch(f"/issues/{release_bug['id']}", json={"is_release_blocker": True})
    assert resp.status_code == 200
    assert resp.json()["is_release_blocker"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("to", ["stream", "backlog"])
async def test_moving_a_blocker_out_of_its_release_clears_the_flag(factories, rig, to):
    admin = factories.admin_client
    bug = await _accepted_bug(factories, rig, release_id=rig["release"].id)
    await admin.patch(f"/issues/{bug['id']}", json={"is_release_blocker": True})

    target = rig["stream_id"] if to == "stream" else None
    resp = await admin.patch(f"/issues/{bug['id']}", json={"release_id": target})
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_release_blocker"] is False

    events = (await admin.get(f"/issues/{bug['id']}/timeline", params={"size": 50})).json()["items"]
    assert any(e["event_type"] == "blocker_cleared" for e in events)


@pytest.mark.asyncio
async def test_moving_a_blocker_between_releases_keeps_the_flag(factories, rig):
    admin = factories.admin_client
    other_release = await factories.release(project_id=rig["project"].id)
    bug = await _accepted_bug(factories, rig, release_id=rig["release"].id)
    await admin.patch(f"/issues/{bug['id']}", json={"is_release_blocker": True})
    resp = await admin.patch(f"/issues/{bug['id']}", json={"release_id": other_release.id})
    assert resp.status_code == 200
    assert resp.json()["is_release_blocker"] is True


# ── Projects have no kind ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_projects_have_no_kind(factories, rig):
    body = (await factories.admin_client.get(f"/projects/id/{rig['project'].id}")).json()
    assert "kind" not in body
    assert body["stream_id"] == rig["stream_id"]
