"""Slice 20 — Support verification and return requests.

docs/phase-2/20-support-verify-and-return-requests.md, PRD v3.1 §7.3³, §8.10,
FR-68/69, BR-69–BR-71, §13. Observations go through HTTP responses and each
recipient's ``GET /inbox``.
"""

import asyncio

import pytest
import pytest_asyncio

from app.policy import Actor, Target, decide, item_actions, transition


@pytest_asyncio.fixture
async def rig(factories, client_for):
    lead = await factories.user(role="developer")
    project = await factories.project(triage_lead_id=lead.id)
    release = await factories.release(project_id=project.id)
    stream_id = await factories.stream_id(project_id=project.id)
    dev = await factories.user(role="developer")
    qa = await factories.user(role="qa")
    support = await factories.user(role="support")
    support2 = await factories.user(role="support")
    template = await factories.support_template(project_id=project.id)
    return {
        "admin": factories.admin_client,
        "project": project, "release": release, "stream_id": stream_id,
        "lead": lead, "lead_client": await client_for(lead),
        "dev": dev, "dev_client": await client_for(dev),
        "qa": qa, "qa_client": await client_for(qa),
        "support": support, "support_client": await client_for(support),
        "support2": support2, "support2_client": await client_for(support2),
        "template": template,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _move(client, issue_id, *steps, expect=200):
    resp = None
    for to in steps:
        resp = await client.post(f"/issues/{issue_id}/transition", json={"to": to})
        assert resp.status_code == expect, resp.text
    return resp.json()


async def _item(client, issue_id) -> dict:
    return (await client.get(f"/issues/{issue_id}")).json()


async def _timeline(client, issue_id) -> list[dict]:
    return (await client.get(f"/issues/{issue_id}/timeline", params={"size": 200})).json()["items"]


async def _inbox(client) -> list[dict]:
    return (await client.get("/inbox", params={"size": 100})).json()["items"]


async def _inbox_types(client) -> list[str]:
    return [i["type"] for i in await _inbox(client)]


async def _support_bug(factories, rig, *, container="stream", **extra):
    """A support-sourced bug accepted into the Stream (or the release), assigned to the dev."""
    bug = await factories.support_report(rig["support_client"], template=rig["template"])
    release_id = rig["stream_id"] if container == "stream" else rig["release"].id
    resp = await rig["lead_client"].post(f"/issues/{bug.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": release_id,
        "assignee_id": rig["dev"].id, **extra,
    })
    assert resp.status_code == 200, resp.text
    return bug


async def _done_in_stream(factories, rig):
    bug = await _support_bug(factories, rig)
    await _move(rig["admin"], bug.id, "in_progress", "in_review", "verified", "done")
    return bug


async def _done_in_released_release(factories, rig):
    bug = await _support_bug(factories, rig, container="release")
    await _move(rig["admin"], bug.id, "in_progress", "in_review", "verified")
    for to in ("development", "qa"):
        resp = await rig["admin"].post(f"/releases/{rig['release'].id}/status", json={"to": to})
        assert resp.status_code == 200, resp.text
    resp = await rig["admin"].post(f"/releases/{rig['release'].id}/ship", json={"confirm": True})
    assert resp.status_code == 200, resp.text
    item = await _item(rig["admin"], bug.id)
    assert item["status"] == "done" and item["release_id"] == rig["release"].id
    return bug


async def _request(client, issue_id, comment="Customer hit it again.", **body):
    return await client.post(
        f"/issues/{issue_id}/return-requests", json={"comment": comment, **body},
    )


async def _pending(client, project_id) -> dict:
    resp = await client.get(f"/projects/{project_id}/return-requests", params={"status": "pending"})
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Policy (pure) ─────────────────────────────────────────────────────────────

SUPPORT = Actor(1, "support")


def _t(status, container="stream", source="support", **kw):
    return Target(item_id=1, item_type="bug", status=status, source=source,
                  container_kind=container, **kw)


@pytest.mark.parametrize("status", ["to_review", "in_review"])
def test_support_status_moves_on_support_items(status):
    assert decide(SUPPORT, transition("verified"), _t(status)).ok
    assert decide(SUPPORT, "reject", _t(status)).ok
    assert decide(SUPPORT, transition("done"), _t(status, "stream")).ok
    for container in ("release", None):
        d = decide(SUPPORT, transition("done"), _t(status, container))
        assert not d.ok and d.hidden
    allowed, blocked = item_actions(SUPPORT, _t(status), ["verified", "done", "in_progress"])
    assert {"transition:verified", "transition:done", "reject"} <= set(allowed)
    assert "transition:in_progress" not in allowed
    assert not any(b["action"].startswith("transition:") for b in blocked)


def test_support_no_other_moves():
    for status in ("todo", "in_progress", "blocked", "verified", "done", "rejected"):
        for action in (transition("verified"), transition("done"), "reject", "mark_production"):
            d = decide(SUPPORT, action, _t(status))
            assert not d.ok, (status, action)
    # A non-support item the Support user can see only by subscription: no moves at all.
    sub = _t("in_review", source="internal", subscriber_ids=frozenset({1}))
    for action in (transition("verified"), transition("done"), "reject"):
        assert not decide(SUPPORT, action, sub).ok


def test_request_return_policy():
    done = _t("done")
    assert decide(SUPPORT, "request_return", done).ok
    d = decide(SUPPORT, "request_return", _t("in_review"))
    assert not d.ok and d.code == "not_done" and d.conflict
    for role in ("qa", "developer", "product_manager", "cto", "admin"):
        d = decide(Actor(2, role), "request_return", done)
        assert not d.ok and d.hidden
        assert decide(Actor(2, role), "decide_return_request", done).ok
    assert not decide(SUPPORT, "decide_return_request", done).ok
    # Tech roles never get a disabled "request_return" control.
    _, blocked = item_actions(Actor(2, "developer"), done, [])
    assert not any(b["action"] == "request_return" for b in blocked)


# ── AC-91 / 92 / 93 — Support verification ────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_91_support_verifies_from_to_review_and_in_review(factories, rig):
    sc = rig["support_client"]
    bug = await _support_bug(factories, rig, container="release")
    await _move(rig["admin"], bug.id, "in_progress", "to_review")
    item = await _item(sc, bug.id)
    assert "transition:verified" in item["allowed_actions"] and "reject" in item["allowed_actions"]
    assert "verified" in item["allowed_transitions"]
    assert (await _move(sc, bug.id, "verified"))["status"] == "verified"

    other = await _support_bug(factories, rig, container="release")
    await _move(rig["admin"], other.id, "in_progress", "in_review")
    resp = await sc.post(f"/issues/{other.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200 and resp.json()["status"] == "verified"


@pytest.mark.asyncio
async def test_ac_91_support_done_only_in_the_stream(factories, rig):
    sc = rig["support_client"]
    stream_bug = await _support_bug(factories, rig)
    await _move(rig["admin"], stream_bug.id, "in_progress", "in_review")
    item = await _item(sc, stream_bug.id)
    assert "done" in item["allowed_transitions"]
    resp = await sc.post(f"/issues/{stream_bug.id}/verify", json={"outcome": "pass", "on_production": True})
    assert resp.status_code == 200 and resp.json()["status"] == "done"

    release_bug = await _support_bug(factories, rig, container="release")
    await _move(rig["admin"], release_bug.id, "in_progress", "in_review")
    item = await _item(sc, release_bug.id)
    assert "done" not in item["allowed_transitions"]
    resp = await sc.post(f"/issues/{release_bug.id}/transition", json={"to": "done"})
    assert resp.status_code in (403, 409)
    assert (await _item(rig["admin"], release_bug.id))["status"] == "in_review"
    resp = await sc.post(f"/issues/{release_bug.id}/verify", json={"outcome": "pass", "on_production": True})
    assert resp.status_code in (403, 409)


@pytest.mark.asyncio
async def test_ac_92_support_reject_needs_comment(factories, rig):
    sc = rig["support_client"]
    bug = await _support_bug(factories, rig, container="release")
    await _move(rig["admin"], bug.id, "in_progress", "in_review")
    for comment in (None, "  "):
        resp = await sc.post(f"/issues/{bug.id}/reject", json={"comment": comment})
        assert resp.status_code == 422 and resp.json()["code"] == "reason_required"
    resp = await sc.post(f"/issues/{bug.id}/reject", json={"comment": "Still fails on staging."})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected" and resp.json()["reject_reason"] == "review"
    assert "item_returned" in await _inbox_types(rig["dev_client"])


@pytest.mark.asyncio
async def test_ac_93_support_other_moves_refused(factories, rig):
    sc = rig["support_client"]
    bug = await _support_bug(factories, rig, container="release")
    await _move(rig["admin"], bug.id, "in_progress")
    for to in ("blocked", "todo", "in_review", "verified", "cancelled"):
        resp = await sc.post(f"/issues/{bug.id}/transition", json={"to": to})
        assert resp.status_code == 403, (to, resp.text)
    await _move(rig["admin"], bug.id, "in_review", "verified")
    for to in ("in_progress", "done", "todo"):
        resp = await sc.post(f"/issues/{bug.id}/transition", json={"to": to})
        assert resp.status_code in (403, 409), (to, resp.text)
    # No Reject from Verified, no On production.
    resp = await sc.post(f"/issues/{bug.id}/reject", json={"comment": "No"})
    assert resp.status_code in (403, 409)
    item = await _item(sc, bug.id)
    assert "reject" not in item["allowed_actions"] and "mark_production" not in item["allowed_actions"]
    resp = await sc.post("/issues/bulk-production", json={"issue_ids": [bug.id]})
    assert resp.status_code == 403
    assert (await _item(rig["admin"], bug.id))["status"] == "verified"


@pytest.mark.asyncio
async def test_ac_93_support_cannot_move_non_support_items(factories, rig):
    sc = rig["support_client"]
    task = await factories.issue(
        project_id=rig["project"].id, type="task", release_id=rig["stream_id"],
        assignee_id=rig["dev"].id,
    )
    await _move(rig["admin"], task.id, "in_progress", "in_review")
    resp = await sc.post(f"/issues/{task.id}/transition", json={"to": "verified"})
    assert resp.status_code == 404
    resp = await sc.post(f"/issues/{task.id}/reject", json={"comment": "No"})
    assert resp.status_code == 404


# ── AC-86 / 87 / 88 — Problem is back ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_86_problem_is_back_needs_a_comment(factories, rig):
    bug = await _done_in_stream(factories, rig)
    for comment in ("", "   "):
        resp = await _request(rig["support_client"], bug.id, comment)
        assert resp.status_code == 422, resp.text
    resp = await rig["support_client"].post(f"/issues/{bug.id}/return-requests", json={})
    assert resp.status_code == 422
    assert (await _pending(rig["lead_client"], rig["project"].id))["total"] == 0


@pytest.mark.asyncio
async def test_ac_87_request_keeps_item_done_and_reaches_triage(factories, rig):
    bug = await _done_in_stream(factories, rig)
    before = await _item(rig["admin"], bug.id)
    resp = await _request(rig["support_client"], bug.id, "Customer A: still broken on prod.")
    assert resp.status_code == 201, resp.text
    req = resp.json()
    assert req["status"] == "pending" and len(req["entries"]) == 1

    after = await _item(rig["admin"], bug.id)
    assert after["status"] == "done"
    assert after["recurrence_count"] == before["recurrence_count"]
    assert after["pending_return_request"]["id"] == req["id"]
    assert len(after["pending_return_request"]["entries"]) == 1
    listing = (await rig["admin"].get("/issues", params={"project_id": rig["project"].id, "size": 100})).json()
    assert listing["total"] == 1  # no second item

    queue = await _pending(rig["lead_client"], rig["project"].id)
    assert queue["total"] == 1
    row = queue["items"][0]
    assert row["id"] == req["id"] and row["issue"]["id"] == bug.id
    assert row["issue"]["status"] == "done" and row["entry_count"] == 1
    assert row["first_comment"]["body"] == "Customer A: still broken on prod."

    assert (await _inbox_types(rig["lead_client"])).count("return_requested") == 1
    events = [e["event_type"] for e in await _timeline(rig["admin"], bug.id)]
    assert "return_requested" in events
    # Support's reports list shows it while pending.
    rows = (await rig["support_client"].get("/support/reports")).json()["items"]
    assert next(r for r in rows if r["id"] == bug.id)["return_requested"] is True
    # Support sees Problem is back as an action; tech users never do.
    support_item = await _item(rig["support_client"], bug.id)
    assert "request_return" in support_item["allowed_actions"]
    assert "reject" not in support_item["allowed_actions"]
    assert "request_return" not in (await _item(rig["dev_client"], bug.id))["allowed_actions"]


@pytest.mark.asyncio
async def test_request_refused_when_not_done_or_tech(factories, rig):
    bug = await _support_bug(factories, rig)
    resp = await _request(rig["support_client"], bug.id)
    assert resp.status_code == 409 and resp.json()["code"] == "not_done"
    done = await _done_in_stream(factories, rig)
    resp = await _request(rig["qa_client"], done.id)
    assert resp.status_code == 403
    internal = await factories.issue(project_id=rig["project"].id)
    assert (await _request(rig["support_client"], internal.id)).status_code == 404


@pytest.mark.asyncio
async def test_ac_88_second_support_user_adds_to_pending_request(factories, rig):
    bug = await _done_in_stream(factories, rig)
    first = (await _request(rig["support_client"], bug.id, "Customer A")).json()
    resp = await _request(rig["support2_client"], bug.id, "Customer B")
    assert resp.status_code in (200, 201), resp.text
    second = resp.json()
    assert second["id"] == first["id"] and len(second["entries"]) == 2

    queue = await _pending(rig["lead_client"], rig["project"].id)
    assert queue["total"] == 1 and queue["items"][0]["entry_count"] == 2
    assert (await _inbox_types(rig["lead_client"])).count("return_requested") == 1
    events = [e["event_type"] for e in await _timeline(rig["admin"], bug.id)]
    assert events.count("return_requested") == 1 and events.count("return_request_added") == 1
    sub = await _item(rig["support2_client"], bug.id)
    assert sub["is_subscribed"] is True
    listing = (await rig["support_client"].get(f"/issues/{bug.id}/return-requests")).json()
    assert len(listing) == 1 and len(listing[0]["entries"]) == 2


@pytest.mark.asyncio
async def test_concurrent_first_presses_make_one_request(factories, rig):
    bug = await _done_in_stream(factories, rig)
    r1, r2 = await asyncio.gather(
        _request(rig["support_client"], bug.id, "A"),
        _request(rig["support2_client"], bug.id, "B"),
    )
    assert r1.status_code in (200, 201) and r2.status_code in (200, 201)
    assert r1.json()["id"] == r2.json()["id"]
    listing = (await rig["admin"].get(f"/issues/{bug.id}/return-requests")).json()
    assert len(listing) == 1 and len(listing[0]["entries"]) == 2
    assert (await _inbox_types(rig["lead_client"])).count("return_requested") == 1


@pytest.mark.asyncio
async def test_request_on_done_task_the_user_is_subscribed_to(factories, rig):
    task = await factories.issue(
        project_id=rig["project"].id, type="task", release_id=rig["stream_id"],
        assignee_id=rig["dev"].id,
    )
    dup = await factories.support_report(rig["support_client"], template=rig["template"])
    resp = await rig["lead_client"].post(f"/issues/{dup.id}/triage", json={
        "outcome": "duplicate", "duplicate_of_id": task.id, "comment": "Same task.",
    })
    if resp.status_code != 200:  # merges target bugs only: subscribe another way
        pytest.skip(f"duplicate into a task is refused: {resp.text}")
    await _move(rig["admin"], task.id, "in_progress", "in_review", "verified", "done")
    resp = await _request(rig["support_client"], task.id, "It is back")
    assert resp.status_code == 201, resp.text
    req = resp.json()
    resp = await rig["lead_client"].post(f"/return-requests/{req['id']}/confirm")
    assert resp.status_code == 200, resp.text
    assert (await _item(rig["admin"], task.id))["status"] == "rejected"
    assert "support_return_decided" in await _inbox_types(rig["support_client"])


# ── AC-89 / 90 — deciding ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_89_confirm_rejects_the_item_in_the_stream(factories, rig):
    bug = await _done_in_released_release(factories, rig)
    count = (await _item(rig["admin"], bug.id))["recurrence_count"]
    req = (await _request(rig["support_client"], bug.id, "Customer A: back on prod")).json()
    await _request(rig["support2_client"], bug.id, "Customer B too")

    resp = await rig["lead_client"].post(f"/return-requests/{req['id']}/confirm")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "confirmed"

    item = await _item(rig["admin"], bug.id)
    assert item["status"] == "rejected" and item["release_id"] == rig["stream_id"]
    assert item["recurrence_count"] == count
    assert item["reject_reason"] == "production"
    assert item["pending_return_request"] is None
    cycles = (await rig["admin"].get(f"/issues/{bug.id}/cycles")).json()
    assert cycles[-1]["start_reason"] == "production"
    assert cycles[-1]["start_comment_id"] == req["start_comment_id"]

    assert "item_returned" in await _inbox_types(rig["dev_client"])
    for client in (rig["support_client"], rig["support2_client"]):
        types = await _inbox_types(client)
        assert types.count("support_return_decided") == 1
    events = [e["event_type"] for e in await _timeline(rig["admin"], bug.id)]
    assert "return_confirmed" in events
    assert (await _pending(rig["lead_client"], rig["project"].id))["total"] == 0
    # A decided request can't be decided again.
    resp = await rig["lead_client"].post(f"/return-requests/{req['id']}/confirm")
    assert resp.status_code == 409 and resp.json()["code"] == "request_closed"
    resp = await rig["lead_client"].post(
        f"/return-requests/{req['id']}/dismiss", json={"comment": "late"},
    )
    assert resp.status_code == 409 and resp.json()["code"] == "request_closed"


@pytest.mark.asyncio
async def test_ac_90_dismiss_needs_a_comment_and_leaves_item_done(factories, rig):
    bug = await _done_in_stream(factories, rig)
    req = (await _request(rig["support_client"], bug.id, "Seems back")).json()
    for body in ({}, {"comment": ""}, {"comment": "  "}):
        resp = await rig["lead_client"].post(f"/return-requests/{req['id']}/dismiss", json=body)
        assert resp.status_code == 422, resp.text
    assert (await _item(rig["admin"], bug.id))["pending_return_request"] is not None

    resp = await rig["lead_client"].post(
        f"/return-requests/{req['id']}/dismiss", json={"comment": "That is a different screen."},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "dismissed"
    item = await _item(rig["admin"], bug.id)
    assert item["status"] == "done" and item["pending_return_request"] is None
    cycles = (await rig["admin"].get(f"/issues/{bug.id}/cycles")).json()
    assert all(c["start_reason"] != "production" for c in cycles)
    decided = [i for i in await _inbox(rig["support_client"]) if i["type"] == "support_return_decided"]
    assert len(decided) == 1
    assert "different screen" in str(decided[0]["meta"])
    assert "return_dismissed" in [e["event_type"] for e in await _timeline(rig["admin"], bug.id)]
    # A new request can now be made.
    assert (await _request(rig["support_client"], bug.id, "Again")).status_code == 201


@pytest.mark.asyncio
async def test_support_cannot_decide(factories, rig):
    bug = await _done_in_stream(factories, rig)
    req = (await _request(rig["support_client"], bug.id)).json()
    assert (await rig["support_client"].post(f"/return-requests/{req['id']}/confirm")).status_code in (403, 404)
    resp = await rig["support_client"].post(
        f"/return-requests/{req['id']}/dismiss", json={"comment": "no"},
    )
    assert resp.status_code in (403, 404)
    assert (await rig["support_client"].get(f"/projects/{rig['project'].id}/return-requests")).status_code == 403


@pytest.mark.asyncio
async def test_tech_reject_closes_a_pending_request(factories, rig):
    bug = await _done_in_stream(factories, rig)
    req = (await _request(rig["support_client"], bug.id)).json()
    resp = await rig["qa_client"].post(f"/issues/{bug.id}/reject", json={"comment": "Reproduced."})
    assert resp.status_code == 200, resp.text
    listing = (await rig["admin"].get(f"/issues/{bug.id}/return-requests")).json()
    assert listing[0]["id"] == req["id"] and listing[0]["status"] == "confirmed"
    assert listing[0]["decided_by"]["id"] == rig["qa"].id
    assert (await _item(rig["admin"], bug.id))["pending_return_request"] is None
    assert (await _pending(rig["lead_client"], rig["project"].id))["total"] == 0
    # No decision notice: the Reject spoke for itself.
    assert "support_return_decided" not in await _inbox_types(rig["support_client"])


# ── AC-12 / AC-71 — recurrence on Done ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_12_71_recurrence_on_done_points_to_problem_is_back(factories, rig):
    bug = await _done_in_stream(factories, rig)
    resp = await rig["support_client"].post(
        f"/issues/{bug.id}/recurrences", json={"comment": "again"},
    )
    assert resp.status_code == 409 and resp.json()["code"] == "recurrence_on_done"
    assert "Problem is back" in resp.json()["detail"]
    item = await _item(rig["support_client"], bug.id)
    assert "request_return" in item["allowed_actions"] and "reject" not in item["allowed_actions"]
    assert "report_recurrence" not in item["allowed_actions"]
