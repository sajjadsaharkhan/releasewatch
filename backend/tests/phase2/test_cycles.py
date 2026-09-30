"""08a Part 2 — cycles (docs/phase-2/cycle-model.md).

Every return of work is a cycle with a ``start_reason``, for bugs and tasks;
cycle 1 starts when the item is placed; the backlog has none.
"""

import pytest


@pytest.fixture
async def rig(factories, client_for):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    stream_id = await factories.stream_id(project_id=project.id)
    dev = await factories.user(role="developer")
    return {
        "project": project, "release": release, "stream_id": stream_id,
        "dev": dev, "dev_client": await client_for(dev),
    }


async def _move(admin, issue_id, to):
    resp = await admin.post(f"/issues/{issue_id}/transition", json={"to": to})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _task(factories, rig, **overrides):
    return await factories.issue(project_id=rig["project"].id, type="task", **overrides)


async def _item(admin, issue_id):
    return (await admin.get(f"/issues/{issue_id}")).json()


# ── Placement starts cycle 1 ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_78_bug_filed_into_release_has_planned_cycle_in_triage(factories, rig):
    bug = await factories.issue(release_id=rig["release"].id)
    assert bug.status == "new"
    cycles = await factories.cycles(bug.id)
    assert [(c["cycle_number"], c["start_reason"], c["release_id"]) for c in cycles] == [
        (1, "planned", rig["release"].id),
    ]
    assert bug.cycle_count == 1 and bug.returned is None


@pytest.mark.asyncio
async def test_backlog_item_has_no_cycle(factories, rig):
    task = await _task(factories, rig)
    assert task.cycle_count == 0
    assert await factories.cycles(task.id) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["patch", "bulk_move", "accept"])
async def test_placement_from_backlog_starts_planned_cycle_one(factories, rig, path):
    admin = factories.admin_client
    if path == "accept":
        item = await factories.issue(project_id=rig["project"].id)
        resp = await admin.post(f"/issues/{item.id}/triage", json={
            "outcome": "accept", "priority": "high", "release_id": rig["stream_id"],
        })
    else:
        item = await _task(factories, rig)
        if path == "patch":
            resp = await admin.patch(f"/issues/{item.id}", json={"release_id": rig["stream_id"]})
        else:
            resp = await admin.post("/issues/bulk-move", json={
                "issue_ids": [item.id], "release_id": rig["stream_id"],
            })
    assert resp.status_code == 200, resp.text
    cycles = await factories.cycles(item.id)
    assert [(c["cycle_number"], c["start_reason"], c["release_id"]) for c in cycles] == [
        (1, "planned", rig["stream_id"]),
    ]


@pytest.mark.asyncio
async def test_move_stream_to_release_updates_open_cycle(factories, rig):
    admin = factories.admin_client
    task = await _task(factories, rig, release_id=rig["stream_id"])
    await _move(admin, task.id, "in_progress")
    resp = await admin.patch(f"/issues/{task.id}", json={"release_id": rig["release"].id})
    assert resp.status_code == 200
    cycles = await factories.cycles(task.id)
    assert len(cycles) == 1
    assert cycles[0]["release_id"] == rig["release"].id
    assert cycles[0]["container_kind"] == "release"


@pytest.mark.asyncio
async def test_done_item_cycle_container_never_changes(factories, rig):
    admin = factories.admin_client
    task = await _task(factories, rig, release_id=rig["release"].id)
    for to in ("in_progress", "in_review", "done"):
        await _move(admin, task.id, to)
    resp = await admin.patch(f"/issues/{task.id}", json={"release_id": rig["stream_id"]})
    assert resp.status_code == 409
    assert (await factories.cycles(task.id))[0]["release_id"] == rig["release"].id


# ── Status stamps and attribution ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_status_moves_stamp_the_current_cycle(factories, rig):
    admin = factories.admin_client
    task = await _task(factories, rig, release_id=rig["stream_id"], assignee_id=rig["dev"].id)
    (cycle,) = await factories.cycles(task.id)
    assert cycle["picked_up_at"] is None and cycle["submitted_at"] is None

    await _move(rig["dev_client"], task.id, "in_progress")
    await _move(rig["dev_client"], task.id, "in_review")
    await _move(admin, task.id, "done")
    (cycle,) = await factories.cycles(task.id)
    assert cycle["picked_up_at"] and cycle["submitted_at"] and cycle["verified_at"]
    assert cycle["closed_at"] is None


@pytest.mark.asyncio
async def test_ac_69_delivered_by_is_assignee_not_actor(factories, rig):
    """An admin moving the status doesn't become the author of the work (CY-05)."""
    admin = factories.admin_client
    task = await _task(factories, rig, release_id=rig["release"].id, assignee_id=rig["dev"].id)
    await _move(admin, task.id, "in_progress")
    await _move(admin, task.id, "in_review")

    (cycle,) = await factories.cycles(task.id)
    assert cycle["delivered_by"]["id"] == rig["dev"].id
    assert cycle["delivered_by"]["id"] != factories.admin_id

    # Written once: a later reassignment moves the cycle's assignee, not the author.
    other = await factories.user(role="developer")
    await admin.patch(f"/issues/{task.id}", json={"assignee_id": other.id})
    (cycle,) = await factories.cycles(task.id)
    assert cycle["assignee_id"] == other.id
    assert cycle["delivered_by"]["id"] == rig["dev"].id


@pytest.mark.asyncio
async def test_ac_70_unassigned_delivery_has_no_author(factories, rig):
    admin = factories.admin_client
    task = await _task(factories, rig, release_id=rig["release"].id)
    await _move(admin, task.id, "in_progress")
    await _move(admin, task.id, "in_review")
    (cycle,) = await factories.cycles(task.id)
    assert cycle["delivered_by"] is None


# ── Returns start the next cycle ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_return_starts_next_cycle_and_marks_item_returned(factories, rig):
    admin = factories.admin_client
    task = await _task(factories, rig, release_id=rig["release"].id, assignee_id=rig["dev"].id)
    await _move(rig["dev_client"], task.id, "in_progress")
    await _move(rig["dev_client"], task.id, "in_review")

    resp = await admin.post(
        f"/issues/{task.id}/transition", json={"to": "todo", "comment": "Fails on Safari"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "todo"
    assert body["cycle_count"] == 2
    assert body["returned"]["reason"] == "review" and body["returned"]["number"] == 1
    assert body["returned"]["comment_id"] is not None

    first, second = await factories.cycles(task.id)
    assert first["closed_at"] is not None
    assert (second["cycle_number"], second["start_reason"]) == (2, "review")
    assert second["start_by"]["id"] == factories.admin_id
    assert second["release_id"] == rig["release"].id

    # The marker lasts until the item is sent to review again.
    await _move(rig["dev_client"], task.id, "in_progress")
    await _move(rig["dev_client"], task.id, "in_review")
    assert (await _item(admin, task.id))["returned"] is None


# ── The backlog deletes cycles ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_73_backlog_move_deletes_cycles_and_replacement_restarts_at_one(factories, rig):
    admin = factories.admin_client
    task = await _task(factories, rig, release_id=rig["release"].id)
    await _move(admin, task.id, "in_progress")
    await _move(admin, task.id, "in_review")
    await admin.post(f"/issues/{task.id}/transition", json={"to": "todo", "comment": "No"})
    assert len(await factories.cycles(task.id)) == 2

    resp = await admin.patch(f"/issues/{task.id}", json={"release_id": None})
    assert resp.status_code == 200
    assert resp.json()["cycle_count"] == 0 and resp.json()["returned"] is None
    assert await factories.cycles(task.id) == []

    resp = await admin.patch(f"/issues/{task.id}", json={"release_id": rig["stream_id"]})
    cycles = await factories.cycles(task.id)
    assert [(c["cycle_number"], c["start_reason"], c["release_id"]) for c in cycles] == [
        (1, "planned", rig["stream_id"]),
    ]


# ── Invariant: current cycle ⇔ container ─────────────────────────────────────


@pytest.mark.asyncio
async def test_current_cycle_iff_container_over_every_mutation_path(factories, rig, client_for):
    admin = factories.admin_client

    async def check(issue_id):
        item = await _item(admin, issue_id)
        cycles = await factories.cycles(issue_id)
        assert (item["release_id"] is None) == (item["cycle_count"] == 0), item
        assert len(cycles) == item["cycle_count"]

    # create: backlog, Stream, Release, and a bug in triage
    backlog = await _task(factories, rig)
    streamed = await _task(factories, rig, release_id=rig["stream_id"])
    released = await _task(factories, rig, release_id=rig["release"].id)
    new_bug = await factories.issue(release_id=rig["release"].id)
    for item in (backlog, streamed, released, new_bug):
        await check(item.id)

    # PATCH moves every way
    for target in (rig["release"].id, rig["stream_id"], None, rig["stream_id"]):
        await admin.patch(f"/issues/{backlog.id}", json={"release_id": target})
        await check(backlog.id)

    # bulk move
    await admin.post("/issues/bulk-move", json={
        "issue_ids": [backlog.id, released.id], "release_id": rig["stream_id"],
    })
    await check(backlog.id)
    await check(released.id)

    # triage: accept into the backlog clears the bug's cycle, needs info keeps it
    await admin.post(f"/issues/{new_bug.id}/triage", json={
        "outcome": "needs_info", "comment": "Which build?",
    })
    await check(new_bug.id)
    await admin.post(f"/issues/{new_bug.id}/triage", json={
        "outcome": "accept", "priority": "low", "release_id": None,
    })
    await check(new_bug.id)

    # status moves, a return, cancel and restore
    for to in ("in_progress", "in_review"):
        await _move(admin, streamed.id, to)
        await check(streamed.id)
    await admin.post(f"/issues/{streamed.id}/transition", json={"to": "todo", "comment": "No"})
    await check(streamed.id)
    await _move(admin, streamed.id, "cancelled")
    await check(streamed.id)
    await _move(admin, streamed.id, "todo")
    await check(streamed.id)

    # a merge into a Done item
    original = await _task(factories, rig, release_id=rig["release"].id)
    for to in ("in_progress", "in_review", "done"):
        await _move(admin, original.id, to)
    await check(original.id)
    report = await factories.issue(project_id=rig["project"].id)
    await admin.post(f"/issues/{report.id}/triage", json={
        "outcome": "duplicate", "duplicate_of_id": original.id,
    })
    await check(original.id)

    # a production return out of a Released release (moves to the Stream)
    shipped = await factories.release(project_id=rig["project"].id)
    item = await _task(factories, rig, release_id=shipped.id)
    for to in ("in_progress", "in_review", "done"):
        await _move(admin, item.id, to)
    await factories.set_release_status(shipped.id, "released")
    await admin.post(f"/issues/{item.id}/returns", json={"comment": "Crashes on prod"})
    await check(item.id)
