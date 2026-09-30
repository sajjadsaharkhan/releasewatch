"""08a Part 3 — returns: Reject, Return from release QA, Problem on production.

docs/phase-2/08a-release-stream-cycles.md Part 3, docs/phase-2/cycle-model.md.

**Workflow stays free (2026-09-30 product decision).** Asked before this slice
was built, the user chose to keep status movement unrestricted: v3's QA gate
(no In progress → Done), "place it first" (AC-56), the Done → To do return-only
rule and self-verification (AC-27) are not enforced. Those ACs' tests below
pin the free behavior so a later change is a deliberate one. Returns, rejects,
cycles, the returned marker and the notification are built as specified.
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


async def _inbox(client):
    resp = await client.get("/inbox", params={"size": 50})
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


async def _delivered(factories, rig, *, type="task", release_id, **overrides):
    """An item assigned to the developer, delivered by them to In review."""
    item = await factories.issue(
        project_id=rig["project"].id, type=type, release_id=release_id,
        assignee_id=rig["dev"].id, **overrides,
    )
    if type == "bug":
        resp = await factories.admin_client.post(f"/issues/{item.id}/triage", json={
            "outcome": "accept", "priority": "high", "release_id": release_id,
            "assignee_id": rig["dev"].id,
        })
        assert resp.status_code == 200, resp.text
    await _move(rig["dev_client"], item.id, "in_progress", "in_review")
    return item


async def _done(factories, rig, **kwargs):
    item = await _delivered(factories, rig, **kwargs)
    await _move(rig["qa_client"], item.id, "done")
    return item


# ── Reject (FR-57) ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_66_reject_requires_comment(factories, rig):
    item = await _delivered(factories, rig, release_id=rig["release"].id)
    # The Reject control — a failed verification — refuses a blank reason.
    for note in (None, "   "):
        resp = await rig["qa_client"].post(
            f"/issues/{item.id}/verify", json={"outcome": "fail", "note": note},
        )
        assert resp.status_code == 422
        assert resp.json()["code"] == "reason_required"
    after = await _item(rig["qa_client"], item.id)
    assert after["status"] == "in_review" and after["cycle_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("via", ["transition", "verify"])
async def test_ac_67_reject_returns_to_todo_with_marker_and_notification(factories, rig, via):
    item = await _delivered(factories, rig, release_id=rig["release"].id)
    if via == "transition":
        resp = await rig["qa_client"].post(f"/issues/{item.id}/transition", json={
            "to": "todo", "comment": "The empty state still shows the spinner.",
        })
    else:
        resp = await rig["qa_client"].post(f"/issues/{item.id}/verify", json={
            "outcome": "fail", "note": "The empty state still shows the spinner.",
        })
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "todo"
    assert body["returned"]["reason"] == "review"
    assert body["returned"]["number"] == 1  # "returned 1"

    cycles = await factories.cycles(item.id)
    assert [c["start_reason"] for c in cycles] == ["planned", "review"]
    assert cycles[1]["start_comment_id"] == body["returned"]["comment_id"]
    assert cycles[0]["delivered_by"]["id"] == rig["dev"].id

    # The reason is a public comment on the item.
    events = (await rig["qa_client"].get(
        f"/issues/{item.id}/timeline", params={"size": 50},
    )).json()["items"]
    comment = next(e for e in events if e["id"] == body["returned"]["comment_id"])
    assert comment["body"] == "The empty state still shows the spinner."
    assert not comment["is_internal"]

    # The assignee is notified with the reason and the comment.
    returned = [i for i in await _inbox(rig["dev_client"]) if i["type"] == "item_returned"]
    assert len(returned) == 1
    assert returned[0]["meta"]["reason"] == "review"
    assert returned[0]["meta"]["cycle_no"] == 2
    assert returned[0]["meta"]["comment_id"] == body["returned"]["comment_id"]


@pytest.mark.asyncio
async def test_ac_68_marker_lasts_until_in_review(factories, rig):
    item = await _delivered(factories, rig, release_id=rig["stream_id"])
    await rig["qa_client"].post(
        f"/issues/{item.id}/transition", json={"to": "todo", "comment": "Wrong copy."},
    )
    body = await _move(rig["dev_client"], item.id, "in_progress")
    assert body["returned"]["reason"] == "review"
    body = await _move(rig["dev_client"], item.id, "in_review")
    assert body["returned"] is None


@pytest.mark.asyncio
async def test_in_review_to_todo_without_comment_is_a_plain_move(factories, rig):
    """Free workflow: without a reason it's an ordinary status change, not a Reject."""
    item = await _delivered(factories, rig, release_id=rig["release"].id)
    body = await _move(rig["qa_client"], item.id, "todo")
    assert body["returned"] is None and body["cycle_count"] == 1


# ── Returns endpoint (FR-59, FR-60) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_25_return_from_release_qa(factories, rig):
    await factories.set_release_status(rig["release"].id, "qa")
    bug = await _done(factories, rig, type="bug", release_id=rig["release"].id)
    assert (await _item(rig["qa_client"], bug.id))["return_reason"] == "release_qa"

    resp = await rig["qa_client"].post(
        f"/issues/{bug.id}/returns", json={"comment": "Checkout crashes on the QA build."},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "todo" and body["release_id"] == rig["release"].id
    assert body["returned"]["reason"] == "release_qa"
    assert [c["start_reason"] for c in await factories.cycles(bug.id)] == [
        "planned", "release_qa",
    ]


@pytest.mark.asyncio
async def test_ac_26_problem_on_production_in_stream(factories, rig):
    task = await _done(factories, rig, release_id=rig["stream_id"])
    assert (await _item(rig["dev_client"], task.id))["return_reason"] == "production"

    resp = await rig["dev_client"].post(
        f"/issues/{task.id}/returns", json={"comment": "Exports time out on production."},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "todo" and body["release_id"] == rig["stream_id"]
    assert body["returned"]["reason"] == "production"


@pytest.mark.asyncio
async def test_ac_64_production_return_moves_to_stream(factories, rig):
    bug = await _done(factories, rig, type="bug", release_id=rig["release"].id)
    await factories.set_release_status(rig["release"].id, "released")

    resp = await rig["qa_client"].post(
        f"/issues/{bug.id}/returns", json={"comment": "Customers see a blank page."},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "todo" and body["release_id"] == rig["stream_id"]
    cycles = await factories.cycles(bug.id)
    assert [(c["start_reason"], c["release_id"]) for c in cycles] == [
        ("planned", rig["release"].id), ("production", rig["stream_id"]),
    ]

    # The release still has no open item.
    open_items = (await rig["qa_client"].get("/issues", params={
        "release_id": rig["release"].id, "statuses": "todo,in_progress,in_review,blocked",
    })).json()["items"]
    assert open_items == []


@pytest.mark.asyncio
async def test_returns_endpoint_decides_the_reason_server_side(factories, rig):
    in_release = await _done(factories, rig, release_id=rig["release"].id)
    in_stream = await _done(factories, rig, release_id=rig["stream_id"])
    for item, expected in ((in_release, "release_qa"), (in_stream, "production")):
        resp = await rig["qa_client"].post(f"/issues/{item.id}/returns", json={
            "comment": "Broken.", "reason": "review",  # the client can't choose
        })
        assert resp.status_code == 200, resp.text
        assert resp.json()["returned"]["reason"] == expected


@pytest.mark.asyncio
async def test_returns_only_from_done(factories, rig):
    item = await _delivered(factories, rig, release_id=rig["release"].id)
    resp = await rig["qa_client"].post(f"/issues/{item.id}/returns", json={"comment": "x"})
    assert resp.status_code == 409 and resp.json()["code"] == "not_done"


@pytest.mark.asyncio
async def test_ac_72_production_return_requires_comment(factories, rig):
    task = await _done(factories, rig, release_id=rig["stream_id"])
    for body in ({}, {"comment": ""}, {"comment": "  "}):
        resp = await rig["dev_client"].post(f"/issues/{task.id}/returns", json=body)
        assert resp.status_code == 422, resp.text
    assert (await _item(rig["dev_client"], task.id))["status"] == "done"


@pytest.mark.asyncio
async def test_ac_71_support_has_no_production_action(factories, rig, client_for):
    template = await factories.support_template(project_id=rig["project"].id)
    report = await factories.support_report(rig["support_client"], template=template)
    admin = factories.admin_client
    await admin.post(f"/issues/{report.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": rig["stream_id"],
    })
    await _move(admin, report.id, "in_progress", "in_review", "done")

    seen = await _item(rig["support_client"], report.id)
    assert "return_item" not in seen["allowed_actions"]
    assert "return_item" not in [b["action"] for b in seen["blocked_actions"]]
    resp = await rig["support_client"].post(f"/issues/{report.id}/returns", json={"comment": "x"})
    assert resp.status_code == 403

    tech = await _item(rig["dev_client"], report.id)
    assert "return_item" in tech["allowed_actions"]


@pytest.mark.asyncio
async def test_support_hears_nothing_about_a_return(factories, rig):
    template = await factories.support_template(project_id=rig["project"].id)
    report = await factories.support_report(rig["support_client"], template=template)
    admin = factories.admin_client
    await admin.post(f"/issues/{report.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": rig["stream_id"],
        "assignee_id": rig["dev"].id,
    })
    await _move(admin, report.id, "in_progress", "in_review", "done")
    before = [i["type"] for i in await _inbox(rig["support_client"])]
    await rig["qa_client"].post(f"/issues/{report.id}/returns", json={"comment": "Again."})
    after = [i["type"] for i in await _inbox(rig["support_client"])]
    assert after == before
    assert "item_returned" in [i["type"] for i in await _inbox(rig["dev_client"])]


# ── No bulk status changes (FR-62, BR-60) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_76_no_bulk_status_endpoint(factories, rig):
    admin = factories.admin_client
    tasks = [
        await factories.issue(project_id=rig["project"].id, type="task") for _ in range(2)
    ]
    ids = [t.id for t in tasks]
    for path in ("/issues/bulk-status", "/issues/bulk-transition", "/issues/bulk-update"):
        resp = await admin.post(path, json={"issue_ids": ids, "status": "done"})
        assert resp.status_code in (404, 405, 422), (path, resp.status_code)
    # Bulk move changes placement only — a status in the body is ignored.
    resp = await admin.post("/issues/bulk-move", json={
        "issue_ids": ids, "release_id": rig["stream_id"], "status": "done",
    })
    assert resp.status_code == 200
    assert {i["status"] for i in resp.json()["items"]} == {"todo"}
    # And no route in the app takes several items together with a status.
    from app.main import app

    offenders = []
    for route in app.routes:
        body = getattr(route, "body_field", None)
        fields = getattr(getattr(body, "type_", None), "model_fields", {}) if body else {}
        if "issue_ids" in fields and ({"status", "to"} & set(fields)):
            offenders.append(route.path)
    assert offenders == []


# ── Gates the user kept off (see module docstring) ────────────────────────────


@pytest.mark.asyncio
async def test_ac_27_reviewer_cannot_verify_own_work(factories, rig):
    """Not enforced (2026-09-22 / 2026-09-30 decisions): the developer who sent
    the work to review may verify it."""
    item = await _delivered(factories, rig, release_id=rig["release"].id)
    body = await _move(rig["dev_client"], item.id, "done")
    assert body["status"] == "done"


@pytest.mark.asyncio
async def test_ac_56_backlog_item_cannot_start(factories, rig):
    """Not enforced (2026-09-30): a backlog item can start; it has no cycle
    until it's placed."""
    task = await factories.issue(project_id=rig["project"].id, type="task")
    body = await _move(rig["dev_client"], task.id, "in_progress")
    assert body["status"] == "in_progress" and body["cycle_count"] == 0


@pytest.mark.asyncio
async def test_ac_57_task_cannot_skip_review(factories, rig):
    """Not enforced (2026-09-30): In progress → Done is still allowed."""
    task = await factories.issue(
        project_id=rig["project"].id, type="task", release_id=rig["stream_id"],
    )
    await _move(rig["dev_client"], task.id, "in_progress")
    body = await _move(rig["dev_client"], task.id, "done")
    assert body["status"] == "done"


@pytest.mark.asyncio
async def test_marker_reason_comment_loads_on_its_own(factories, rig):
    item = await _delivered(factories, rig, release_id=rig["stream_id"])
    body = (await rig["qa_client"].post(f"/issues/{item.id}/transition", json={
        "to": "todo", "comment": "Label overlaps the icon.",
    })).json()
    comment_id = body["returned"]["comment_id"]
    resp = await rig["dev_client"].get(f"/issues/{item.id}/timeline/{comment_id}")
    assert resp.status_code == 200
    assert resp.json()["body"] == "Label overlaps the icon."
    other = await factories.issue(project_id=rig["project"].id, type="task")
    resp = await rig["dev_client"].get(f"/issues/{other.id}/timeline/{comment_id}")
    assert resp.status_code == 404
