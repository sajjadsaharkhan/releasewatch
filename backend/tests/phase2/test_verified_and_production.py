"""Slice 19 — Verified, and Done means on production.

docs/phase-2/19-verified-and-production.md, PRD v3.1 §9 and BR-67–BR-76,
contract in docs/phase-2/19-contract.md. Observations go through HTTP
responses, each recipient's ``GET /inbox`` and the Telegram recorder.
"""

import asyncio
from pathlib import Path

import pytest
import pytest_asyncio
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.db.session import get_engine
from app.workflow import Workflow

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent


@pytest_asyncio.fixture
async def rig(factories, client_for):
    lead = await factories.user(role="developer")
    project = await factories.project(triage_lead_id=lead.id)
    release = await factories.release(project_id=project.id)
    stream_id = await factories.stream_id(project_id=project.id)
    dev = await factories.user(role="developer")
    qa = await factories.user(role="qa")
    support = await factories.user(role="support")
    template = await factories.support_template(project_id=project.id)
    return {
        "admin": factories.admin_client,
        "project": project, "release": release, "stream_id": stream_id,
        "lead": lead, "lead_client": await client_for(lead),
        "dev": dev, "dev_client": await client_for(dev),
        "qa": qa, "qa_client": await client_for(qa),
        "support": support, "support_client": await client_for(support),
        "template": template,
    }


async def _move(client, issue_id, *steps, expect=200):
    resp = None
    for to in steps:
        resp = await client.post(f"/issues/{issue_id}/transition", json={"to": to})
        assert resp.status_code == expect, resp.text
    return resp.json()


async def _item(client, issue_id) -> dict:
    return (await client.get(f"/issues/{issue_id}")).json()


async def _task(factories, rig, *, container="stream", assignee=True, **fields):
    release_id = rig["stream_id"] if container == "stream" else rig["release"].id
    return await factories.issue(
        project_id=rig["project"].id, type="task", release_id=release_id,
        assignee_id=rig["dev"].id if assignee else None, **fields,
    )


async def _verified(factories, rig, *, container="stream", **fields):
    """A task in ``container`` that QA verified (In progress → In review → /verify)."""
    task = await _task(factories, rig, container=container, **fields)
    await _move(rig["admin"], task.id, "in_progress", "in_review")
    resp = await rig["qa_client"].post(f"/issues/{task.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "verified"
    return task


async def _timeline(client, issue_id) -> list[dict]:
    return (await client.get(f"/issues/{issue_id}/timeline", params={"size": 200})).json()["items"]


async def _inbox_types(client) -> list[str]:
    return [i["type"] for i in (await client.get("/inbox", params={"size": 100})).json()["items"]]


async def _to_qa(admin, release_id):
    for to in ("development", "qa"):
        resp = await admin.post(f"/releases/{release_id}/status", json={"to": to})
        assert resp.status_code == 200, resp.text


async def _cycles(admin, issue_id) -> list[dict]:
    return (await admin.get(f"/issues/{issue_id}/cycles")).json()


async def _support_bug_in_stream(factories, rig):
    """A support-sourced bug in the Stream, assigned to the developer."""
    bug = await factories.support_report(rig["support_client"], template=rig["template"])
    resp = await rig["lead_client"].post(f"/issues/{bug.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": rig["stream_id"],
        "assignee_id": rig["dev"].id,
    })
    assert resp.status_code == 200, resp.text
    return bug


# ── Workflow module (pure) ────────────────────────────────────────────────────


@pytest.mark.parametrize("item_type", ["bug", "task"])
def test_done_gate_in_workflow_module(item_type):
    ctx = {"container_kind": "release"}
    check = Workflow.can_transition(item_type, "verified", "done", ctx)
    assert not check.ok and check.code == "done_at_ship"
    assert "done" not in Workflow.allowed_targets(item_type, "in_review", ctx).allowed
    assert "verified" in Workflow.allowed_targets(item_type, "in_review", ctx).allowed
    assert Workflow.can_transition(item_type, "verified", "done", {**ctx, "via_ship": True}).ok
    stream = {"container_kind": "stream"}
    assert Workflow.can_transition(item_type, "in_review", "done", stream).ok
    assert "done" in Workflow.allowed_targets(item_type, "verified", stream).allowed
    # No container (the backlog) or no context: unchanged free workflow.
    assert Workflow.can_transition(item_type, "todo", "done", {}).ok


# ── AC-24 — Verified is not Done ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_24_verify_moves_to_verified_and_done_is_a_deploy_move(
    factories, rig, telegram,
):
    bug = await _support_bug_in_stream(factories, rig)
    await telegram.link_telegram(rig["support"])
    admin = rig["admin"]
    await _move(admin, bug.id, "in_progress", "in_review")

    resp = await rig["qa_client"].post(f"/issues/{bug.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "verified"
    assert body["verified_at"] is not None and body["completed_at"] is None
    # Support hears "fixed" only at Done — never at Verified.
    assert "support_done" not in await _inbox_types(rig["support_client"])
    assert "support_done" not in [t for t, _ in telegram.sent_to(rig["support"])]

    done = await _move(admin, bug.id, "done")
    assert done["status"] == "done" and done["completed_at"] is not None
    assert done["verified_at"] == body["verified_at"]
    assert "support_done" in await _inbox_types(rig["support_client"])
    assert "support_done" in [t for t, _ in telegram.sent_to(rig["support"])]


@pytest.mark.asyncio
async def test_verified_move_is_notified_and_recorded(factories, rig):
    task = await _task(factories, rig)
    await _move(rig["admin"], task.id, "in_progress", "in_review")
    await _move(rig["admin"], task.id, "verified")
    events = [
        e for e in await _timeline(rig["admin"], task.id) if e["event_type"] == "status_changed"
    ]
    assert events[-1]["meta"]["from"] == "in_review" and events[-1]["meta"]["to"] == "verified"
    assert "status_changed" in await _inbox_types(rig["dev_client"])


@pytest.mark.asyncio
async def test_verify_on_production_in_the_stream_goes_straight_to_done(factories, rig):
    task = await _task(factories, rig)
    await _move(rig["admin"], task.id, "in_progress", "in_review")
    resp = await rig["qa_client"].post(
        f"/issues/{task.id}/verify", json={"outcome": "pass", "on_production": True},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "done"


@pytest.mark.asyncio
async def test_verify_on_production_of_a_release_item_is_refused(factories, rig):
    task = await _task(factories, rig, container="release")
    await _move(rig["admin"], task.id, "in_progress", "in_review")
    resp = await rig["qa_client"].post(
        f"/issues/{task.id}/verify", json={"outcome": "pass", "on_production": True},
    )
    assert resp.status_code == 409 and resp.json()["code"] == "done_at_ship"
    assert (await _item(rig["admin"], task.id))["status"] == "in_review"


# ── AC-57 — the Done gate ─────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("frm", ["todo", "in_progress", "in_review", "verified"])
async def test_ac_57_release_item_cannot_be_moved_to_done(factories, rig, frm):
    task = await _task(factories, rig, container="release")
    if frm != "todo":
        await _move(rig["admin"], task.id, *{
            "in_progress": ("in_progress",),
            "in_review": ("in_progress", "in_review"),
            "verified": ("in_progress", "in_review", "verified"),
        }[frm])
    item = await _item(rig["admin"], task.id)
    assert "done" not in item["allowed_transitions"]
    assert "verified" in item["allowed_transitions"] or frm == "verified"
    resp = await rig["admin"].post(f"/issues/{task.id}/transition", json={"to": "done"})
    assert resp.status_code == 409 and resp.json()["code"] == "done_at_ship"
    assert (await _item(rig["admin"], task.id))["status"] == frm


@pytest.mark.asyncio
async def test_ac_57_stream_items_list_both_verified_and_done(factories, rig):
    task = await _task(factories, rig)
    await _move(rig["admin"], task.id, "in_progress", "in_review")
    allowed = (await _item(rig["admin"], task.id))["allowed_transitions"]
    assert "verified" in allowed and "done" in allowed


# ── AC-83 — straight to Done in the Stream ────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_83_in_review_straight_to_done_sets_verified_and_completed(factories, rig):
    task = await _task(factories, rig)
    await _move(rig["admin"], task.id, "in_progress", "in_review")
    body = await _move(rig["admin"], task.id, "done")
    assert body["verified_at"] is not None and body["completed_at"] is not None
    cycle = (await _cycles(rig["admin"], task.id))[-1]
    assert cycle["verified_at"] is not None


@pytest.mark.asyncio
async def test_verified_timestamp_is_never_overwritten(factories, rig):
    task = await _verified(factories, rig)
    first = (await _item(rig["admin"], task.id))["verified_at"]
    await _move(rig["admin"], task.id, "done")
    assert (await _item(rig["admin"], task.id))["verified_at"] == first


# ── AC-25 — Reject from Verified ──────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("container", ["release", "stream"])
async def test_ac_25_reject_from_verified_is_release_qa_in_its_container(
    factories, rig, container,
):
    task = await _verified(factories, rig, container=container)
    item = await _item(rig["qa_client"], task.id)
    assert "reject" in item["allowed_actions"]
    resp = await rig["qa_client"].post(
        f"/issues/{task.id}/reject", json={"comment": "Fails on staging."},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["release_id"] == (rig["release"].id if container == "release" else rig["stream_id"])
    cycles = await _cycles(rig["admin"], task.id)
    assert cycles[-1]["start_reason"] == "release_qa"
    assert body["verified_at"] is None


@pytest.mark.asyncio
async def test_reject_from_done_in_the_stream_is_production(factories, rig):
    task = await _verified(factories, rig)
    await _move(rig["admin"], task.id, "done")
    resp = await rig["qa_client"].post(f"/issues/{task.id}/reject", json={"comment": "Down."})
    assert resp.status_code == 200, resp.text
    assert (await _cycles(rig["admin"], task.id))[-1]["start_reason"] == "production"


@pytest.mark.asyncio
async def test_reject_from_review_stays_review(factories, rig):
    task = await _task(factories, rig, container="release")
    await _move(rig["admin"], task.id, "in_progress", "in_review")
    resp = await rig["qa_client"].post(f"/issues/{task.id}/reject", json={"comment": "No."})
    assert resp.status_code == 200, resp.text
    assert (await _cycles(rig["admin"], task.id))[-1]["start_reason"] == "review"


# ── AC-50 / AC-51 — merge ─────────────────────────────────────────────────────


async def _merge_into(factories, rig, original_id):
    """File a bug and triage it as a duplicate of ``original_id``."""
    dup = await factories.issue(project_id=rig["project"].id, release_id=None)
    resp = await rig["lead_client"].post(f"/issues/{dup.id}/triage", json={
        "outcome": "duplicate", "duplicate_of_id": original_id,
        "comment": "Same problem again.",
    })
    assert resp.status_code == 200, resp.text


async def _bug(factories, rig, container="stream"):
    """A triaged bug in ``container``, assigned to the developer (bugs are filed
    into triage, then accepted into a container)."""
    bug = await factories.issue(project_id=rig["project"].id)
    resp = await rig["lead_client"].post(f"/issues/{bug.id}/triage", json={
        "outcome": "accept", "priority": "high", "assignee_id": rig["dev"].id,
        "release_id": rig["stream_id"] if container == "stream" else rig["release"].id,
    })
    assert resp.status_code == 200, resp.text
    return bug


@pytest.mark.asyncio
async def test_ac_50_merge_into_done_rejects_with_production_and_keeps_the_count(
    factories, rig,
):
    original = await _bug(factories, rig)
    await _move(rig["admin"], original.id, "in_progress", "in_review", "done")
    before = (await _item(rig["admin"], original.id))["recurrence_count"]
    await _merge_into(factories, rig, original.id)
    item = await _item(rig["admin"], original.id)
    assert item["status"] == "rejected"
    assert item["recurrence_count"] == before
    assert (await _cycles(rig["admin"], original.id))[-1]["start_reason"] == "production"


@pytest.mark.asyncio
async def test_ac_51_merge_into_verified_changes_nothing_but_the_count(factories, rig):
    original = await _bug(factories, rig, container="release")
    await _move(rig["admin"], original.id, "in_progress", "in_review", "verified")
    before = (await _item(rig["admin"], original.id))["recurrence_count"]
    cycles_before = len(await _cycles(rig["admin"], original.id))
    await _merge_into(factories, rig, original.id)
    item = await _item(rig["admin"], original.id)
    assert item["status"] == "verified"
    assert item["recurrence_count"] == before + 1
    assert len(await _cycles(rig["admin"], original.id)) == cycles_before


@pytest.mark.asyncio
async def test_ac_79_recurrence_on_verified_is_allowed(factories, rig):
    bug = await _bug(factories, rig)
    await _move(rig["admin"], bug.id, "in_progress", "in_review", "verified")
    item = await _item(rig["qa_client"], bug.id)
    assert "report_recurrence" in item["allowed_actions"]
    resp = await rig["qa_client"].post(
        f"/issues/{bug.id}/recurrences", json={"comment": "Happened again."},
    )
    assert resp.status_code == 201, resp.text
    assert (await _item(rig["admin"], bug.id))["status"] == "verified"


# ── AC-45 / AC-59 / AC-58 — progress, cancel, immobility ──────────────────────


@pytest.mark.asyncio
async def test_ac_45_progress_counts_verified(factories, rig):
    rid = rig["release"].id
    a = await _task(factories, rig, container="release")
    await _task(factories, rig, container="release")
    await _move(rig["admin"], a.id, "verified")
    resp = await rig["admin"].get(f"/releases/{rid}")
    assert resp.json()["progress"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_ac_59_cancel_is_refused_with_a_verified_item(factories, rig):
    task = await _task(factories, rig, container="release")
    await _move(rig["admin"], task.id, "verified")
    resp = await rig["admin"].post(f"/releases/{rig['release'].id}/cancel")
    assert resp.status_code == 409 and resp.json()["code"] == "release_has_done_items"
    assert "cancelled" not in (await rig["admin"].get(f"/releases/{rig['release'].id}")).json()[
        "allowed_transitions"
    ]


@pytest.mark.asyncio
async def test_ac_58_verified_item_cannot_change_container(factories, rig):
    task = await _task(factories, rig, container="release")
    await _move(rig["admin"], task.id, "verified")
    for body in ({"release_id": rig["stream_id"]}, {"release_id": None}):
        resp = await rig["admin"].patch(f"/issues/{task.id}", json=body)
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "delivered_item_immobile"
    resp = await rig["admin"].post("/issues/bulk-move", json={
        "issue_ids": [task.id], "release_id": rig["stream_id"],
    })
    assert resp.status_code == 409 and resp.json()["code"] == "delivered_item_immobile"


@pytest.mark.asyncio
async def test_ac_58_done_item_cannot_change_container_either(factories, rig):
    task = await _verified(factories, rig)
    await _move(rig["admin"], task.id, "done")
    resp = await rig["admin"].patch(f"/issues/{task.id}", json={"release_id": rig["release"].id})
    assert resp.status_code == 409 and resp.json()["code"] == "delivered_item_immobile"


# ── AC-60 / AC-61 — ship ──────────────────────────────────────────────────────


async def _ship_rig(factories, rig):
    """Release with 2 Verified, 2 To do, 1 In review, 1 Rejected, 1 Cancelled."""
    admin = rig["admin"]
    verified = []
    for _ in range(2):
        t = await _task(factories, rig, container="release")
        await _move(admin, t.id, "verified")
        verified.append(t)
    todo = [await _task(factories, rig, container="release") for _ in range(2)]
    in_review = await _task(factories, rig, container="release")
    await _move(admin, in_review.id, "in_progress", "in_review")
    rejected = await _task(factories, rig, container="release")
    await _move(admin, rejected.id, "in_progress", "in_review")
    resp = await admin.post(f"/issues/{rejected.id}/reject", json={"comment": "Nope."})
    assert resp.status_code == 200, resp.text
    cancelled = await _task(factories, rig, container="release")
    await _move(admin, cancelled.id, "cancelled")
    await _to_qa(admin, rig["release"].id)
    return {
        "verified": verified, "todo": todo, "in_review": in_review,
        "rejected": rejected, "cancelled": cancelled,
    }


@pytest.mark.asyncio
async def test_ac_60_61_ship_preview_and_ship(factories, rig, client_for, telegram):
    items = await _ship_rig(factories, rig)
    admin, rid = rig["admin"], rig["release"].id
    resp = await admin.get(f"/releases/{rid}/ship-preview")
    assert resp.status_code == 200, resp.text
    preview = resp.json()
    assert preview["to_production"] == 2
    assert preview["to_backlog"] == {"todo": 2, "in_review": 1, "rejected": 1}
    assert preview["total_to_backlog"] == 4
    assert set(preview["go_nogo"]) == {"status", "note", "by_id", "at"}

    resp = await admin.post(f"/releases/{rid}/ship", json={"confirm": True})
    assert resp.status_code == 200, resp.text
    released_at = resp.json()["released_at"]

    for t in items["verified"]:
        item = await _item(admin, t.id)
        assert item["status"] == "done" and item["release_id"] == rid
        assert item["completed_at"] == released_at
        assert item["verified_at"] is not None
        events = [
            e for e in await _timeline(admin, t.id) if e["event_type"] == "status_changed"
        ]
        assert [(e["meta"]["from"], e["meta"]["to"], e["meta"]["reason"]) for e in events][-1] == (
            "verified", "done", "ship",
        )
    for t in (*items["todo"], items["in_review"], items["rejected"]):
        item = await _item(admin, t.id)
        assert item["release_id"] is None and item["status"] == "todo"
    cancelled = await _item(admin, items["cancelled"].id)
    assert cancelled["status"] == "cancelled" and cancelled["release_id"] == rid

    activity = (await admin.get(f"/releases/{rid}/activity")).json()
    shipped = next(e for e in activity["events"] if e["event_type"] == "shipped")
    assert shipped["meta"]["to_production"] == 2


@pytest.mark.asyncio
async def test_ship_sends_one_support_done_per_item_and_none_before(
    factories, rig, telegram,
):
    admin = rig["admin"]
    bug = await factories.support_report(rig["support_client"], template=rig["template"])
    resp = await rig["lead_client"].post(f"/issues/{bug.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": rig["release"].id,
        "assignee_id": rig["dev"].id,
    })
    assert resp.status_code == 200, resp.text
    await _move(admin, bug.id, "in_progress", "in_review", "verified")
    await _to_qa(admin, rig["release"].id)
    assert "support_done" not in await _inbox_types(rig["support_client"])

    resp = await admin.post(f"/releases/{rig['release'].id}/ship", json={"confirm": True})
    assert resp.status_code == 200, resp.text
    types = await _inbox_types(rig["support_client"])
    assert types.count("support_done") == 1


@pytest.mark.asyncio
async def test_ship_makes_no_status_changed_noise_per_item(factories, rig):
    items = await _ship_rig(factories, rig)
    before = await _inbox_types(rig["dev_client"])
    await rig["admin"].post(f"/releases/{rig['release'].id}/ship", json={"confirm": True})
    after = await _inbox_types(rig["dev_client"])
    assert after.count("status_changed") == before.count("status_changed")
    assert after.count("release_shipped") == before.count("release_shipped") + 1
    assert items  # silence unused


# ── AC-81 — On production ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_81_bulk_production_makes_items_done_with_one_batch(factories, rig):
    admin = rig["admin"]
    tasks = [await _verified(factories, rig) for _ in range(3)]
    ids = [t.id for t in tasks]
    resp = await rig["dev_client"].post("/issues/bulk-production", json={"issue_ids": ids})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {i["id"] for i in body["issues"]} == set(ids)
    assert all(i["status"] == "done" and i["completed_at"] for i in body["issues"])
    batch_id = body["batch_id"]
    assert batch_id
    for t in tasks:
        events = [
            e for e in await _timeline(admin, t.id) if e["event_type"] == "status_changed"
        ]
        last = events[-1]
        assert last["meta"]["reason"] == "on_production"
        assert (last["meta"]["from"], last["meta"]["to"]) == ("verified", "done")
        assert last["meta"]["batch_id"] == batch_id


@pytest.mark.asyncio
async def test_ac_81_bulk_production_is_all_or_nothing(factories, rig):
    good = await _verified(factories, rig)
    in_review = await _task(factories, rig)
    await _move(rig["admin"], in_review.id, "in_progress", "in_review")
    in_release = await _verified(factories, rig, container="release")
    resp = await rig["dev_client"].post("/issues/bulk-production", json={
        "issue_ids": [good.id, in_review.id, in_release.id],
    })
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["code"] == "not_verified_in_stream"
    assert set(body["issue_ids"]) == {in_review.id, in_release.id}
    assert (await _item(rig["admin"], good.id))["status"] == "verified"


@pytest.mark.asyncio
async def test_ac_81_bulk_production_refuses_unknown_ids_and_support(factories, rig):
    good = await _verified(factories, rig)
    resp = await rig["dev_client"].post(
        "/issues/bulk-production", json={"issue_ids": [good.id, 99999999]},
    )
    assert resp.status_code == 409 and resp.json()["issue_ids"] == [99999999]
    resp = await rig["support_client"].post(
        "/issues/bulk-production", json={"issue_ids": [good.id]},
    )
    assert resp.status_code == 403, resp.text
    assert (await _item(rig["admin"], good.id))["status"] == "verified"


@pytest.mark.asyncio
@pytest.mark.parametrize("ids", [[], list(range(1, 102))])
async def test_bulk_production_takes_one_to_a_hundred_ids(rig, ids):
    resp = await rig["dev_client"].post("/issues/bulk-production", json={"issue_ids": ids})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_mark_production_action_is_on_stream_items_for_tech_roles(factories, rig):
    task = await _verified(factories, rig)
    assert "mark_production" in (await _item(rig["dev_client"], task.id))["allowed_actions"]


# ── AC-39 / AC-74 / AC-75 — queue ─────────────────────────────────────────────


async def _queue_ids(client):
    q = (await client.get("/users/me/queue")).json()
    return (
        [e["issue"]["id"] for e in q["groups"]["pinned"]],
        [e["issue"]["id"] for e in q["groups"]["rest"]],
    )


@pytest.mark.asyncio
async def test_ac_39_verified_releases_the_pin_and_leaves_the_queue(factories, rig):
    a = await _task(factories, rig, priority="medium")
    b = await _task(factories, rig, priority="medium")
    resp = await rig["dev_client"].post("/users/me/queue/pins", json={"issue_id": a.id})
    assert resp.status_code == 200, resp.text
    await _move(rig["admin"], a.id, "verified")
    pinned, rest = await _queue_ids(rig["dev_client"])
    assert pinned == [] and rest == [b.id]
    # Verified → Done leaves the dormant entry alone.
    await _move(rig["admin"], a.id, "done")
    assert await _queue_ids(rig["dev_client"]) == ([], [b.id])


@pytest.mark.asyncio
@pytest.mark.parametrize("via_done", [False, True])
async def test_ac_74_75_reject_from_verified_or_done_restores_the_position(
    factories, rig, via_done,
):
    first = await _task(factories, rig, priority="high")
    second = await _task(factories, rig, priority="medium")
    third = await _task(factories, rig, priority="low")
    pinned_item = await _task(factories, rig, priority="low")
    await rig["dev_client"].post("/users/me/queue/pins", json={"issue_id": pinned_item.id})
    await _move(rig["admin"], second.id, "in_progress", "in_review", "verified")
    if via_done:
        await _move(rig["admin"], second.id, "done")
    pinned, rest = await _queue_ids(rig["dev_client"])
    assert pinned == [pinned_item.id] and rest == [first.id, third.id]

    resp = await rig["qa_client"].post(f"/issues/{second.id}/reject", json={"comment": "Back."})
    assert resp.status_code == 200, resp.text
    pinned, rest = await _queue_ids(rig["dev_client"])
    # Back at its old place, never above the pin.
    assert pinned == [pinned_item.id] and rest == [first.id, second.id, third.id]


@pytest.mark.asyncio
async def test_my_work_board_has_a_verified_column(factories, rig):
    task = await _task(factories, rig)
    await _move(rig["admin"], task.id, "verified")
    resp = await rig["dev_client"].get("/users/me/board")
    assert resp.status_code == 200, resp.text
    columns = {c["status"]: c for c in resp.json()["columns"]}
    assert [i["id"] for i in columns["verified"]["items"]] == [task.id]


@pytest.mark.asyncio
async def test_release_board_has_a_verified_column_before_done(factories, rig):
    task = await _task(factories, rig, container="release")
    await _move(rig["admin"], task.id, "verified")
    resp = await rig["admin"].get(f"/releases/{rig['release'].id}/board")
    assert resp.status_code == 200, resp.text
    columns = resp.json()["columns"]
    order = [c["status"] for c in columns]
    assert order.index("verified") == order.index("in_review") + 1
    assert order.index("verified") < order.index("done")
    verified = next(c for c in columns if c["status"] == "verified")
    assert [i["id"] for i in verified["items"]] == [task.id]


# ── Backlog: a Verified item can't be in it ───────────────────────────────────


@pytest.mark.asyncio
async def test_verified_item_cannot_go_to_the_backlog(factories, rig):
    task = await _verified(factories, rig)
    resp = await rig["admin"].patch(f"/issues/{task.id}", json={"release_id": None})
    assert resp.status_code == 409 and resp.json()["code"] == "delivered_item_immobile"


# ── AC-85 — migration ─────────────────────────────────────────────────────────


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


PREVIOUS_HEAD = "c0d1e2f3a4b5"


async def _rows(engine, ids):
    async with engine.connect() as conn:
        rows = (await conn.execute(
            text("SELECT id, status, completed_at, verified_at FROM issues WHERE id = ANY(:ids)"),
            {"ids": list(ids.values())},
        )).all()
    by_id = {r[0]: r for r in rows}
    return {name: by_id[i] for name, i in ids.items()}


async def _entry_left(engine, issue_id):
    async with engine.connect() as conn:
        return (await conn.execute(
            text("SELECT left_at, is_pinned FROM queue_entries WHERE issue_id = :i"),
            {"i": issue_id},
        )).first()


@pytest.mark.asyncio
async def test_ac_85_migration_up_and_down(factories, rig, db_session):
    admin = rig["admin"]
    # Done in an unshipped release / Done in a Released release / Done in the Stream.
    in_release = await _task(factories, rig, container="release")
    await _move(admin, in_release.id, "in_progress", "in_review", "verified")
    in_stream = await _verified(factories, rig)
    await _move(admin, in_stream.id, "done")
    other_release = await factories.release(project_id=rig["project"].id)
    shipped = await factories.issue(
        project_id=rig["project"].id, type="task", release_id=other_release.id,
        assignee_id=rig["dev"].id,
    )
    await _move(admin, shipped.id, "in_progress", "in_review", "verified")
    await _to_qa(admin, other_release.id)
    resp = await admin.post(f"/releases/{other_release.id}/ship", json={"confirm": True})
    assert resp.status_code == 200, resp.text
    ids = {"in_release": in_release.id, "in_stream": in_stream.id, "shipped": shipped.id}

    engine = get_engine()
    await db_session.rollback()
    try:
        await asyncio.to_thread(command.downgrade, _alembic_config(), PREVIOUS_HEAD)
        down = await _rows(engine, ids)
        # v3 shape: Verified in a release is Done, completed = verified.
        assert down["in_release"][1] == "done"
        assert down["in_release"][2] == down["in_release"][3] is not None
        assert down["in_stream"][1] == "done" and down["shipped"][1] == "done"

        # Upgrade: only Done in an unshipped release becomes Verified.
        await asyncio.to_thread(command.upgrade, _alembic_config(), "head")
        up = await _rows(engine, ids)
        assert up["in_release"][1] == "verified"
        assert up["in_release"][2] is None and up["in_release"][3] is not None
        assert up["in_stream"][1] == "done" and up["in_stream"][2] is not None
        assert up["shipped"][1] == "done" and up["shipped"][2] is not None
        entry = await _entry_left(engine, in_release.id)
        assert entry is not None and entry[0] is not None and entry[1] is False

        # Idempotent: a second run changes nothing.
        await asyncio.to_thread(command.downgrade, _alembic_config(), PREVIOUS_HEAD)
        await asyncio.to_thread(command.upgrade, _alembic_config(), "head")
        assert await _rows(engine, ids) == up
    finally:
        await asyncio.to_thread(command.upgrade, _alembic_config(), "head")


@pytest.mark.asyncio
async def test_release_item_blocks_done_with_done_at_ship(factories, rig):
    task = await _task(factories, rig, container="release")
    item = await _item(rig["dev_client"], task.id)
    assert {"to": "done", "code": "done_at_ship", "detail": "Done when the release ships."} in (
        item["blocked_transitions"]
    )
    stream = await _item(rig["dev_client"], (await _task(factories, rig)).id)
    assert all(b["to"] != "done" for b in stream["blocked_transitions"])
