"""09a — To review, Rejected, and one Reject action.

docs/phase-2/09a-review-queue-and-rejected.md, ADR 0004.

``to_review`` and ``rejected`` are statuses for bugs and tasks. The workflow
stays free except that nothing enters ``rejected`` through ``/transition``
(409 ``use_reject``): the ways in are ``POST /reject`` and a merge into a Done
item. Cycles still record every pass and classify it; the UI reads the status.
"""

import pytest


@pytest.fixture
async def rig(factories, client_for):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    stream_id = await factories.stream_id(project_id=project.id)
    dev = await factories.user(role="developer")
    qa = await factories.user(role="qa")
    support = await factories.user(role="support")
    return {
        "project": project, "release": release, "stream_id": stream_id,
        "dev": dev, "dev_client": await client_for(dev),
        "qa": qa, "qa_client": await client_for(qa),
        "support": support, "support_client": await client_for(support),
    }


async def _move(client, issue_id, *steps):
    body = None
    for to in steps:
        resp = await client.post(f"/issues/{issue_id}/transition", json={"to": to})
        assert resp.status_code == 200, resp.text
        body = resp.json()
    return body


async def _item(client, issue_id):
    return (await client.get(f"/issues/{issue_id}")).json()


async def _reject(client, issue_id, comment="The empty state still shows the spinner."):
    return await client.post(f"/issues/{issue_id}/reject", json={"comment": comment})


async def _inbox(client):
    resp = await client.get("/inbox", params={"size": 50})
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


async def _timeline(client, issue_id):
    resp = await client.get(f"/issues/{issue_id}/timeline", params={"size": 100})
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


async def _task_at(factories, rig, *steps, release_id=None):
    """A task assigned to the developer, in ``release_id`` (the Stream by
    default), walked through ``steps``."""
    task = await factories.issue(
        project_id=rig["project"].id, type="task",
        release_id=release_id or rig["stream_id"], assignee_id=rig["dev"].id,
    )
    if steps:
        await _move(rig["dev_client"], task.id, *steps)
    return task


# ── Statuses ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_to_review_is_an_ordinary_status_for_bugs_and_tasks(factories, rig):
    task = await _task_at(factories, rig, "in_progress", "to_review")
    assert (await _item(rig["dev_client"], task.id))["status"] == "to_review"

    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["stream_id"])
    await factories.admin_client.post(f"/issues/{bug.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": rig["stream_id"],
    })
    body = await _move(rig["dev_client"], bug.id, "in_progress", "to_review", "in_review")
    assert body["status"] == "in_review"
    assert "to_review" in body["allowed_transitions"]


@pytest.mark.asyncio
@pytest.mark.parametrize("start", ["todo", "in_progress", "in_review", "done", "blocked"])
async def test_nothing_enters_rejected_through_transition(factories, rig, start):
    steps = {
        "todo": (), "in_progress": ("in_progress",),
        "in_review": ("in_progress", "in_review"),
        "done": ("in_progress", "in_review", "done"), "blocked": ("blocked",),
    }[start]
    task = await _task_at(factories, rig, *steps)
    body = await _item(rig["dev_client"], task.id)
    assert "rejected" not in body["allowed_transitions"]
    assert "transition:rejected" not in body["allowed_actions"]

    resp = await factories.admin_client.post(
        f"/issues/{task.id}/transition", json={"to": "rejected", "comment": "No."},
    )
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "use_reject"
    assert (await _item(rig["dev_client"], task.id))["status"] == start


@pytest.mark.asyncio
async def test_patch_cannot_set_rejected_either(factories, rig):
    task = await _task_at(factories, rig, "in_progress", "in_review")
    resp = await factories.admin_client.patch(f"/issues/{task.id}", json={"status": "rejected"})
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "use_reject"


@pytest.mark.asyncio
async def test_in_review_to_todo_with_a_comment_is_a_plain_move(factories, rig):
    task = await _task_at(factories, rig, "in_progress", "in_review")
    resp = await rig["qa_client"].post(f"/issues/{task.id}/transition", json={
        "to": "todo", "comment": "Actually not ready.",
    })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "todo"
    assert body["cycle_number"] == 1
    assert [c["start_reason"] for c in await factories.cycles(task.id)] == ["planned"]


@pytest.mark.asyncio
async def test_verify_fail_is_refused_with_use_reject(factories, rig):
    task = await _task_at(factories, rig, "in_progress", "in_review")
    resp = await rig["qa_client"].post(f"/issues/{task.id}/verify", json={
        "outcome": "fail", "note": "Still broken.",
    })
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "use_reject"
    assert (await _item(rig["qa_client"], task.id))["status"] == "in_review"


# ── Reject ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("start, container, reason", [
    ("to_review", "stream", "review"),
    ("in_review", "release", "review"),
    ("done", "release", "release_qa"),
    ("done", "stream", "production"),
])
async def test_reject_lands_in_rejected_and_starts_the_next_cycle(
    factories, rig, start, container, reason,
):
    steps = {
        "to_review": ("in_progress", "to_review"),
        "in_review": ("in_progress", "to_review", "in_review"),
        "done": ("in_progress", "in_review", "done"),
    }[start]
    release_id = rig["stream_id"] if container == "stream" else rig["release"].id
    task = await _task_at(factories, rig, *steps, release_id=release_id)
    assert "reject" in (await _item(rig["qa_client"], task.id))["allowed_actions"]

    resp = await _reject(rig["qa_client"], task.id, "Checkout crashes.")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["release_id"] == release_id
    assert body["cycle_number"] == 2
    assert body["reject_reason"] == reason
    assert "reject" not in body["allowed_actions"]
    assert "returned" not in body and "return_reason" not in body

    cycles = await factories.cycles(task.id)
    assert [c["start_reason"] for c in cycles] == ["planned", reason]
    assert cycles[1]["start_comment_id"] == body["reject_comment_id"]
    assert cycles[0]["closed_at"] is not None

    # One plain public comment carries the reason.
    events = await _timeline(rig["qa_client"], task.id)
    comments = [e for e in events if e["event_type"] == "comment"]
    assert len(comments) == 1
    assert comments[0]["id"] == body["reject_comment_id"]
    assert comments[0]["body"] == "Checkout crashes."
    assert not comments[0]["is_internal"]
    assert "return_reason" not in (comments[0]["meta"] or {})
    # The status change says it was a reject.
    moves = [e for e in events if e["event_type"] == "status_changed"]
    assert moves[-1]["meta"]["to"] == "rejected"
    assert moves[-1]["meta"]["reason"] == "reject"

    # The assignee hears about it.
    returned = [i for i in await _inbox(rig["dev_client"]) if i["type"] == "item_returned"]
    assert len(returned) == 1
    assert returned[0]["meta"]["reason"] == reason
    assert returned[0]["meta"]["cycle_no"] == 2
    assert returned[0]["meta"]["comment_id"] == body["reject_comment_id"]


@pytest.mark.asyncio
async def test_reject_works_for_bugs(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["release"].id)
    await factories.admin_client.post(f"/issues/{bug.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": rig["release"].id,
        "assignee_id": rig["dev"].id,
    })
    await _move(rig["dev_client"], bug.id, "in_progress", "to_review")
    resp = await _reject(rig["qa_client"], bug.id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"
    assert resp.json()["reject_reason"] == "review"


@pytest.mark.asyncio
@pytest.mark.parametrize("start", ["todo", "in_progress", "blocked", "rejected"])
async def test_reject_refused_from_other_statuses(factories, rig, start):
    steps = {
        "todo": (), "in_progress": ("in_progress",), "blocked": ("blocked",),
        "rejected": ("in_progress", "to_review"),
    }[start]
    task = await _task_at(factories, rig, *steps)
    if start == "rejected":
        assert (await _reject(rig["qa_client"], task.id)).status_code == 200
    assert "reject" not in (await _item(rig["qa_client"], task.id))["allowed_actions"]
    resp = await _reject(rig["qa_client"], task.id)
    assert resp.status_code == 409, resp.text
    assert resp.json()["code"] == "not_rejectable"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [{}, {"comment": ""}, {"comment": "   "}])
async def test_reject_requires_a_comment(factories, rig, payload):
    task = await _task_at(factories, rig, "in_progress", "in_review")
    resp = await rig["qa_client"].post(f"/issues/{task.id}/reject", json=payload)
    assert resp.status_code == 422, resp.text
    body = await _item(rig["qa_client"], task.id)
    assert body["status"] == "in_review" and body["cycle_number"] == 1


@pytest.mark.asyncio
async def test_support_cannot_reject(factories, rig):
    template = await factories.support_template(project_id=rig["project"].id)
    report = await factories.support_report(rig["support_client"], template=template)
    admin = factories.admin_client
    await admin.post(f"/issues/{report.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": rig["stream_id"],
    })
    await _move(admin, report.id, "in_progress", "in_review")
    seen = await _item(rig["support_client"], report.id)
    assert "reject" not in seen["allowed_actions"]
    assert "reject" not in [b["action"] for b in seen["blocked_actions"]]
    resp = await _reject(rig["support_client"], report.id)
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_reject_from_a_released_release_moves_to_the_stream(factories, rig):
    task = await _task_at(
        factories, rig, "in_progress", "in_review", "done", release_id=rig["release"].id,
    )
    await factories.set_release_status(rig["release"].id, "released")
    resp = await _reject(rig["qa_client"], task.id, "Customers see a blank page.")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["release_id"] == rig["stream_id"]
    assert body["reject_reason"] == "production"
    cycles = await factories.cycles(task.id)
    assert [(c["start_reason"], c["release_id"]) for c in cycles] == [
        ("planned", rig["release"].id), ("production", rig["stream_id"]),
    ]


@pytest.mark.asyncio
async def test_merge_into_a_done_item_rejects_it(factories, rig):
    original = await _task_at(
        factories, rig, "in_progress", "in_review", "done", release_id=rig["release"].id,
    )
    report = await factories.issue(project_id=rig["project"].id)
    resp = await factories.admin_client.post(f"/issues/{report.id}/triage", json={
        "outcome": "duplicate", "duplicate_of_id": original.id,
    })
    assert resp.status_code == 200, resp.text
    body = await _item(rig["qa_client"], original.id)
    assert body["status"] == "rejected"
    assert body["reject_reason"] == "release_qa"
    assert body["cycle_number"] == 2
    assert body["reject_comment_id"] is not None
    # The status change records that a merge caused it, not a manual Reject.
    moves = [
        e for e in await _timeline(rig["qa_client"], original.id)
        if e["event_type"] == "status_changed"
    ]
    assert (moves[-1]["meta"]["to"], moves[-1]["meta"]["reason"]) == ("rejected", "merge")


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["returns", "reopen"])
async def test_returns_and_reopen_are_aliases_of_reject(factories, rig, path):
    task = await _task_at(factories, rig, "in_progress", "in_review", "done")
    resp = await rig["qa_client"].post(f"/issues/{task.id}/{path}", json={"comment": "Broken."})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected" and body["reject_reason"] == "production"
    # Still Done items only.
    other = await _task_at(factories, rig, "in_progress", "in_review")
    resp = await rig["qa_client"].post(f"/issues/{other.id}/{path}", json={"comment": "x"})
    assert resp.status_code == 409 and resp.json()["code"] == "not_done"


# ── Leaving Rejected ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_picking_up_rejected_work_keeps_the_cycle_badge(factories, rig):
    task = await _task_at(factories, rig, "in_progress", "in_review")
    await _reject(rig["qa_client"], task.id)
    body = await _move(rig["dev_client"], task.id, "in_progress")
    assert body["status"] == "in_progress"
    assert body["cycle_number"] == 2
    assert body["reject_reason"] is None and body["reject_comment_id"] is None
    cycles = await factories.cycles(task.id)
    assert cycles[1]["picked_up_at"] is not None


@pytest.mark.asyncio
async def test_dragging_rejected_to_todo_is_just_a_move(factories, rig):
    task = await _task_at(factories, rig, "in_progress", "in_review")
    await _reject(rig["qa_client"], task.id)
    body = await _move(rig["dev_client"], task.id, "todo")
    assert body["status"] == "todo" and body["cycle_number"] == 2
    assert len(await factories.cycles(task.id)) == 2


@pytest.mark.asyncio
async def test_rejected_item_moving_between_containers_stays_rejected(factories, rig):
    task = await _task_at(factories, rig, "in_progress", "in_review")
    await _reject(rig["qa_client"], task.id)
    resp = await factories.admin_client.patch(
        f"/issues/{task.id}", json={"release_id": rig["release"].id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected" and body["cycle_number"] == 2
    assert [c["release_id"] for c in await factories.cycles(task.id)][-1] == rig["release"].id


@pytest.mark.asyncio
async def test_rejected_item_moved_to_backlog_becomes_todo(factories, rig):
    task = await _task_at(factories, rig, "in_progress", "in_review")
    await _reject(rig["qa_client"], task.id)
    resp = await factories.admin_client.patch(f"/issues/{task.id}", json={"release_id": None})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "todo"
    assert body["cycle_number"] is None and body["release_id"] is None
    assert await factories.cycles(task.id) == []
    moves = [
        e for e in await _timeline(rig["qa_client"], task.id)
        if e["event_type"] == "status_changed"
    ]
    assert (moves[-1]["meta"]["from"], moves[-1]["meta"]["to"]) == ("rejected", "todo")


@pytest.mark.asyncio
async def test_shipping_a_release_with_a_rejected_item_leaves_it_todo(factories, rig):
    task = await _task_at(factories, rig, "in_progress", "in_review", release_id=rig["release"].id)
    await _reject(rig["qa_client"], task.id)
    await factories.set_release_status(rig["release"].id, "released")
    body = await _item(rig["qa_client"], task.id)
    assert body["status"] == "todo" and body["release_id"] is None
    assert await factories.cycles(task.id) == []


# ── Cycle timestamps (CY-05) ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submitted_at_on_first_of_to_review_or_in_review(factories, rig, client_for):
    other_dev = await factories.user(role="developer")
    task = await _task_at(factories, rig, "in_progress", "to_review")
    first = (await factories.cycles(task.id))[0]
    assert first["submitted_at"] is not None
    assert first["delivered_by"]["id"] == rig["dev"].id

    # Reassigned while waiting; QA's pickup doesn't overwrite the delivery.
    await factories.admin_client.patch(f"/issues/{task.id}", json={"assignee_id": other_dev.id})
    await _move(rig["qa_client"], task.id, "in_review")
    again = (await factories.cycles(task.id))[0]
    assert again["submitted_at"] == first["submitted_at"]
    assert again["delivered_by"]["id"] == rig["dev"].id

    # Skipping To review still stamps the delivery on In review.
    skipped = await _task_at(factories, rig, "in_progress", "in_review")
    assert (await factories.cycles(skipped.id))[0]["submitted_at"] is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("via", ["to_review", "in_review"])
async def test_verified_at_on_done_from_either_review_status(factories, rig, via):
    steps = ("in_progress", "to_review") if via == "to_review" else ("in_progress", "in_review")
    task = await _task_at(factories, rig, *steps)
    await _move(rig["qa_client"], task.id, "done")
    assert (await factories.cycles(task.id))[0]["verified_at"] is not None


# ── Listing ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cycle_number_is_null_in_the_backlog(factories, rig):
    task = await factories.issue(project_id=rig["project"].id, type="task")
    assert (await _item(rig["dev_client"], task.id))["cycle_number"] is None


@pytest.mark.asyncio
async def test_statuses_filter_accepts_the_new_statuses(factories, rig):
    waiting = await _task_at(factories, rig, "in_progress", "to_review")
    rejected = await _task_at(factories, rig, "in_progress", "in_review")
    await _reject(rig["qa_client"], rejected.id)
    resp = await rig["qa_client"].get("/issues", params={
        "project_id": rig["project"].id, "statuses": "to_review,rejected",
    })
    assert resp.status_code == 200, resp.text
    assert {i["id"] for i in resp.json()["items"]} == {waiting.id, rejected.id}
