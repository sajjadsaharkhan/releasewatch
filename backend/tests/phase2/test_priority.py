"""03a Part 1 (docs/phase-2/03a-data-model-refactor.md): one shared priority
scale for bugs and tasks — ``critical | high | medium | low`` — replacing
bug ``severity`` and task ``priority`` 1–4.

BR-16: a New or Needs info bug may have no priority; accepting a bug
requires one; a task is created with ``medium``.
"""

import pytest


@pytest.fixture
async def rig(factories):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    return {"project": project, "release": release}


# ── BR-16: defaults ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_new_bug_has_no_priority(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["release"].id)
    assert bug.status == "new"
    assert bug.priority is None


@pytest.mark.asyncio
async def test_bug_may_be_filed_with_a_priority(factories, rig):
    bug = await factories.issue(
        project_id=rig["project"].id, release_id=rig["release"].id, priority="high",
    )
    assert bug.priority == "high"


@pytest.mark.asyncio
async def test_task_defaults_to_medium_priority(factories, rig):
    task = await factories.issue(project_id=rig["project"].id, type="task")
    assert task.type == "task"
    assert task.priority == "medium"


@pytest.mark.asyncio
async def test_task_keeps_an_explicit_priority(factories, rig):
    task = await factories.issue(project_id=rig["project"].id, type="task", priority="low")
    assert task.priority == "low"


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["blocker", "major", "minor", "enhancement", 2])
async def test_old_scales_are_rejected(factories, rig, value):
    resp = await factories.admin_client.post("/issues", json={
        "title": "old scale", "project_id": rig["project"].id,
        "release_id": rig["release"].id, "priority": value,
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_severity_field_is_gone(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["release"].id)
    assert not hasattr(bug, "severity")


# ── AC-16: accept requires a priority ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_16_priority_required_on_accept(factories, rig):
    developer = await factories.user(role="developer")
    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["release"].id)
    admin = factories.admin_client

    resp = await admin.post(f"/issues/{bug.id}/triage", json={"outcome": "accept", "assignee_id": developer.id})
    assert resp.status_code == 422
    locs = [tuple(e["loc"]) for e in resp.json()["detail"]]
    assert ("body", "accept", "priority") in locs  # the triage body is a tagged union (06)

    resp = await admin.post(
        f"/issues/{bug.id}/triage", json={"outcome": "accept", "assignee_id": developer.id, "priority": None},
    )
    assert resp.status_code == 422

    still_new = (await admin.get(f"/issues/{bug.id}")).json()
    assert still_new["status"] == "new"
    assert still_new["priority"] is None

    resp = await admin.post(
        f"/issues/{bug.id}/triage", json={"outcome": "accept", "assignee_id": developer.id, "priority": "medium"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "todo"
    assert resp.json()["priority"] == "medium"


# ── Changing priority: timeline + notification ──────────────────────────────


@pytest.mark.asyncio
async def test_priority_change_records_event_and_notifies_assignee(factories, client_for, rig):
    developer = await factories.user(role="developer")
    bug = await factories.issue(
        project_id=rig["project"].id, release_id=rig["release"].id, assignee_id=developer.id,
    )
    admin = factories.admin_client

    resp = await admin.patch(f"/issues/{bug.id}", json={"priority": "critical"})
    assert resp.status_code == 200
    assert resp.json()["priority"] == "critical"

    timeline = (await admin.get(f"/issues/{bug.id}/timeline")).json()["items"]
    changes = [e for e in timeline if e["event_type"] == "priority_changed"]
    assert len(changes) == 1
    assert changes[0]["meta"] == {"from": None, "to": "critical"}

    dev_client = await client_for(developer)
    inbox = (await dev_client.get("/inbox")).json()["items"]
    assert "priority_changed" in [item["type"] for item in inbox]


@pytest.mark.asyncio
async def test_task_priority_is_editable(factories, rig):
    task = await factories.issue(project_id=rig["project"].id, type="task")
    resp = await factories.admin_client.patch(f"/issues/{task.id}", json={"priority": "high"})
    assert resp.status_code == 200
    assert resp.json()["priority"] == "high"


# ── List: filter and sort read the one field for both types ─────────────────


@pytest.mark.asyncio
async def test_filter_by_priority_spans_both_types(factories, rig):
    pid = rig["project"].id
    high_bug = await factories.issue(project_id=pid, release_id=rig["release"].id, priority="high")
    high_task = await factories.issue(project_id=pid, type="task", priority="high")
    medium_task = await factories.issue(project_id=pid, type="task")

    resp = await factories.admin_client.get(
        "/issues", params={"project_id": pid, "priority": "high"},
    )
    assert resp.status_code == 200
    ids = {i["id"] for i in resp.json()["items"]}
    assert ids == {high_bug.id, high_task.id}
    assert medium_task.id not in ids


@pytest.mark.asyncio
async def test_sort_by_priority_puts_unrated_last(factories, rig):
    pid = rig["project"].id
    rid = rig["release"].id
    unrated = await factories.issue(project_id=pid, release_id=rid)
    low = await factories.issue(project_id=pid, type="task", priority="low")
    critical = await factories.issue(project_id=pid, release_id=rid, priority="critical")
    medium = await factories.issue(project_id=pid, type="task")

    resp = await factories.admin_client.get(
        "/issues", params={"project_id": pid, "sort": "priority"},
    )
    assert resp.status_code == 200
    order = [i["id"] for i in resp.json()["items"]]
    assert order == [critical.id, medium.id, low.id, unrated.id]
