"""Slice 09 — releases and the Stream.

docs/phase-2/09-releases-and-stream.md (PRD v3 §8.7, FR-46–FR-54, BR-47, BR-48,
BR-55–BR-57, BR-62; AC-45, AC-46, AC-59–AC-63; §13 overdue notice).
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db.session import get_engine
from app.release_lifecycle import allowed_targets, can_change, can_ship


# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def rig(factories):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    stream_id = await factories.stream_id(project_id=project.id)
    return {"project": project, "release": release, "stream_id": stream_id}


async def _item(factories, container_id, project_id, status="todo", **overrides):
    """A task in ``container_id`` moved to ``status`` (the workflow is free)."""
    task = await factories.issue(
        project_id=project_id, release_id=container_id, type="task", **overrides,
    )
    if status != "todo":
        resp = await factories.admin_client.post(
            f"/issues/{task.id}/transition", json={"to": status},
        )
        assert resp.status_code == 200, resp.text
    return task


async def _to_qa(admin, release_id):
    for to in ("development", "qa"):
        resp = await admin.post(f"/releases/{release_id}/status", json={"to": to})
        assert resp.status_code == 200, resp.text
    return resp.json()


async def _release(admin, release_id):
    resp = await admin.get(f"/releases/{release_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _backdate_completed(issue_id: int, when: datetime) -> None:
    """No endpoint sets when an item was completed — bootstrap it directly."""
    async with get_engine().begin() as conn:
        await conn.execute(
            text("UPDATE issues SET completed_at = :w WHERE id = :i"), {"w": when, "i": issue_id},
        )


async def _set_target(admin, release_id, when):
    resp = await admin.patch(
        f"/releases/{release_id}",
        json={"target_date": when.isoformat() if when else None},
    )
    assert resp.status_code == 200, resp.text


# ── Lifecycle module (pure) ──────────────────────────────────────────────────


ALLOWED_MANUAL = {
    ("planning", "development"), ("development", "qa"), ("qa", "development"),
    ("planning", "cancelled"), ("development", "cancelled"), ("qa", "cancelled"),
}
STATUSES = ("planning", "development", "qa", "released", "cancelled")


@pytest.mark.parametrize("frm", STATUSES)
@pytest.mark.parametrize("to", STATUSES)
def test_lifecycle_transition_table(frm, to):
    check = can_change("release", frm, to)
    assert check.ok == ((frm, to) in ALLOWED_MANUAL), (frm, to, check)
    if (frm, to) == ("qa", "released"):
        assert check.code == "use_ship"
    elif to == "released":
        assert check.code in ("ship_only_from_qa", "release_final", "no_change")


@pytest.mark.parametrize("frm", STATUSES)
def test_lifecycle_released_only_through_ship(frm):
    assert can_change("release", frm, "released", via_ship=True).ok == (frm == "qa")
    assert can_ship("release", frm).ok == (frm == "qa")


@pytest.mark.parametrize("frm", ("planning", "development", "qa"))
def test_lifecycle_cancel_refused_with_done_items(frm):
    check = can_change("release", frm, "cancelled", has_done_items=True)
    assert not check.ok and check.code == "release_has_done_items"
    assert "cancelled" not in allowed_targets("release", frm, has_done_items=True)


@pytest.mark.parametrize("to", STATUSES)
def test_lifecycle_refuses_every_stream_change(to):
    check = can_change("stream", None, to, via_ship=True)
    assert not check.ok and check.code == "stream_immutable"
    assert allowed_targets("stream", None) == []


def test_lifecycle_final_statuses_offer_nothing():
    assert allowed_targets("release", "released") == []
    assert allowed_targets("release", "cancelled") == []


# ── Create, edit, lifecycle over the API (FR-49, FR-50) ──────────────────────


@pytest.mark.asyncio
async def test_create_release_under_project_starts_in_planning(factories, rig):
    admin = factories.admin_client
    resp = await admin.post(f"/projects/{rig['project'].id}/releases", json={
        "version": "3.0.0",
        "description": "Big one",
        "code_freeze_date": "2026-10-10",
        "target_date": "2026-10-20T00:00:00Z",
        "staging_url": "https://staging.example.com",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "planning"
    assert body["code_freeze_date"] == "2026-10-10"
    assert body["staging_url"] == "https://staging.example.com"
    assert body["allowed_transitions"] == ["development", "cancelled"]

    listed = (await admin.get(f"/projects/{rig['project'].id}/releases")).json()
    assert {r["id"] for r in listed} == {rig["release"].id, body["id"]}


@pytest.mark.asyncio
async def test_lifecycle_over_the_api(factories, rig):
    admin = factories.admin_client
    rid = rig["release"].id
    body = await _to_qa(admin, rid)
    assert body["status"] == "qa"
    assert body["allowed_transitions"] == ["development", "cancelled"]

    back = await admin.post(f"/releases/{rid}/status", json={"to": "development"})
    assert back.status_code == 200 and back.json()["status"] == "development"

    for bad in ("planning", "released"):
        resp = await admin.post(f"/releases/{rid}/status", json={"to": bad})
        assert resp.status_code == 409, resp.text
    # PATCH can't sneak a status past the lifecycle either.
    resp = await admin.patch(f"/releases/{rid}", json={"status": "released"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_status_change_on_the_stream_is_refused(factories, rig):
    resp = await factories.admin_client.post(
        f"/releases/{rig['stream_id']}/status", json={"to": "development"},
    )
    assert resp.status_code == 409 and resp.json()["code"] == "stream_immutable"
    resp = await factories.admin_client.post(f"/releases/{rig['stream_id']}/cancel")
    assert resp.status_code == 409 and resp.json()["code"] == "stream_immutable"


@pytest.mark.asyncio
async def test_qa_user_cannot_manage_releases(factories, client_for, rig):
    qa = await factories.user(role="qa")
    c = await client_for(qa)
    resp = await c.post(f"/releases/{rig['release'].id}/status", json={"to": "development"})
    assert resp.status_code == 403
    resp = await c.post(f"/projects/{rig['project'].id}/releases", json={"version": "9"})
    assert resp.status_code == 403


# ── Progress and Overdue (BR-47, BR-48) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_45_progress_excludes_cancelled(factories, rig):
    rid, pid = rig["release"].id, rig["project"].id
    for status, n in (("cancelled", 2), ("done", 4), ("todo", 3), ("in_progress", 1)):
        for _ in range(n):
            await _item(factories, rid, pid, status)
    body = await _release(factories.admin_client, rid)
    assert body["progress"] == pytest.approx(0.5)
    assert body["counts"]["done"] == 4
    assert body["counts"]["cancelled"] == 2
    assert body["counts"]["todo"] == 3


@pytest.mark.asyncio
async def test_progress_is_null_with_no_non_cancelled_items(factories, rig):
    body = await _release(factories.admin_client, rig["release"].id)
    assert body["progress"] is None
    await _item(factories, rig["release"].id, rig["project"].id, "cancelled")
    assert (await _release(factories.admin_client, rig["release"].id))["progress"] is None


@pytest.mark.asyncio
async def test_ac_46_no_overdue_without_target_date(factories, rig, clock):
    admin = factories.admin_client
    rid = rig["release"].id
    clock.set(datetime(2030, 1, 1, tzinfo=UTC))
    assert (await _release(admin, rid))["is_overdue"] is False

    await _set_target(admin, rid, datetime(2029, 12, 1, tzinfo=UTC))
    assert (await _release(admin, rid))["is_overdue"] is True

    await _set_target(admin, rid, datetime(2030, 2, 1, tzinfo=UTC))
    assert (await _release(admin, rid))["is_overdue"] is False


@pytest.mark.asyncio
async def test_released_or_cancelled_release_is_never_overdue(factories, rig, clock):
    admin = factories.admin_client
    other = await factories.release(project_id=rig["project"].id)
    for rid in (rig["release"].id, other.id):
        await _set_target(admin, rid, datetime(2020, 1, 1, tzinfo=UTC))
        assert (await _release(admin, rid))["is_overdue"] is True
    await _to_qa(admin, rig["release"].id)
    resp = await admin.post(f"/releases/{rig['release'].id}/ship", json={"confirm": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_overdue"] is False
    resp = await admin.post(f"/releases/{other.id}/cancel")
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_overdue"] is False


# ── Cancel (BR-55) ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_59_release_with_done_item_cannot_be_cancelled(factories, client_for, rig):
    product_manager = await factories.user(role="product_manager")
    c = await client_for(product_manager)
    await _item(factories, rig["release"].id, rig["project"].id, "done")
    before = await _release(factories.admin_client, rig["release"].id)
    assert "cancelled" not in before["allowed_transitions"]

    for resp in (
        await c.post(f"/releases/{rig['release'].id}/cancel"),
        await c.post(f"/releases/{rig['release'].id}/status", json={"to": "cancelled"}),
    ):
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "release_has_done_items"
    assert (await _release(factories.admin_client, rig["release"].id))["status"] == "planning"


@pytest.mark.asyncio
async def test_cancel_moves_open_items_to_the_backlog(factories, rig):
    admin = factories.admin_client
    pid = rig["project"].id
    assignee = await factories.user(role="developer")
    open_item = await _item(
        factories, rig["release"].id, pid, "in_progress", assignee_id=assignee.id,
    )
    dropped = await _item(factories, rig["release"].id, pid, "cancelled")

    resp = await admin.post(f"/releases/{rig['release'].id}/cancel")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"

    item = (await admin.get(f"/issues/{open_item.id}")).json()
    assert item["release_id"] is None
    assert item["status"] == "todo"
    assert item["assignee_id"] == assignee.id
    assert item["backlog_category_id"] == (await factories.default_category(project_id=pid)).id
    assert await factories.cycles(open_item.id) == []
    # A Cancelled item stays where it was.
    assert (await admin.get(f"/issues/{dropped.id}")).json()["release_id"] == rig["release"].id


# ── Ship (FR-53, BR-56) ──────────────────────────────────────────────────────


async def _ac_60_release(factories, rig):
    rid, pid = rig["release"].id, rig["project"].id
    assignee = await factories.user(role="developer")
    items = {}
    for status, n in (("done", 5), ("todo", 2), ("in_progress", 1), ("in_review", 1)):
        items[status] = [
            await _item(factories, rid, pid, status, assignee_id=assignee.id) for _ in range(n)
        ]
    await _to_qa(factories.admin_client, rid)
    return items, assignee


@pytest.mark.asyncio
async def test_ac_60_ship_preview_counts_not_done_by_status(factories, client_for, rig):
    await _ac_60_release(factories, rig)
    cto = await factories.user(role="cto")
    c = await client_for(cto)
    resp = await c.post(
        f"/releases/{rig['release'].id}/go-nogo", json={"decision": "approved", "note": "LGTM"},
    )
    assert resp.status_code == 200, resp.text

    resp = await c.get(f"/releases/{rig['release'].id}/ship-preview")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["not_done"] == {
        "todo": 2, "rejected": 0, "in_progress": 1, "to_review": 0, "in_review": 1, "blocked": 0,
    }
    assert body["total_not_done"] == 4
    assert body["go_nogo"]["status"] == "approved"
    assert body["go_nogo"]["note"] == "LGTM"


@pytest.mark.asyncio
async def test_ac_61_ship_moves_open_items_to_backlog_default_without_cycles(
    factories, client_for, rig,
):
    items, assignee = await _ac_60_release(factories, rig)
    admin = factories.admin_client
    pid, rid = rig["project"].id, rig["release"].id
    default = await factories.default_category(project_id=pid)
    other_cat = await factories.backlog_category(project_id=pid)
    moved_one = items["todo"][0]
    await admin.patch(f"/issues/{moved_one.id}", json={"backlog_category_id": other_cat.id})

    cto = await factories.user(role="cto")
    resp = await (await client_for(cto)).post(f"/releases/{rid}/ship", json={"confirm": True})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "released"
    assert body["released_at"] is not None

    for done in items["done"]:
        item = (await admin.get(f"/issues/{done.id}")).json()
        assert item["release_id"] == rid and item["status"] == "done"
    for status in ("todo", "in_progress", "in_review"):
        for it in items[status]:
            item = (await admin.get(f"/issues/{it.id}")).json()
            assert item["release_id"] is None
            assert item["status"] == "todo"
            assert item["assignee_id"] == assignee.id
            assert item["backlog_category_id"] == default.id
            assert await factories.cycles(it.id) == []

    backlog = (await admin.get(f"/projects/{pid}/backlog")).json()
    backlog_ids = {i["id"] for i in backlog["items"]}
    assert {it.id for s in ("todo", "in_progress", "in_review") for it in items[s]} <= backlog_ids


@pytest.mark.asyncio
async def test_ship_keeps_assignee_of_an_in_progress_item(factories, rig):
    # Pins arrive with the personal queue (slice 10); the assignee is what exists today.
    admin = factories.admin_client
    dev = await factories.user(role="developer")
    it = await _item(factories, rig["release"].id, rig["project"].id, "in_progress",
                     assignee_id=dev.id)
    await _to_qa(admin, rig["release"].id)
    resp = await admin.post(f"/releases/{rig['release'].id}/ship", json={"confirm": True})
    assert resp.status_code == 200, resp.text
    item = (await admin.get(f"/issues/{it.id}")).json()
    assert (item["status"], item["release_id"], item["assignee_id"]) == ("todo", None, dev.id)


@pytest.mark.asyncio
async def test_ac_62_ship_only_from_qa(factories, rig):
    admin = factories.admin_client
    rid = rig["release"].id
    body = await _release(admin, rid)
    assert "ship_release" not in body["allowed_actions"]
    resp = await admin.post(f"/releases/{rid}/ship", json={"confirm": True})
    assert resp.status_code == 409 and resp.json()["code"] == "ship_only_from_qa"
    resp = await admin.get(f"/releases/{rid}/ship-preview")
    assert resp.status_code == 409

    await _to_qa(admin, rid)
    assert "ship_release" in (await _release(admin, rid))["allowed_actions"]


@pytest.mark.asyncio
async def test_ship_requires_confirm(factories, rig):
    admin = factories.admin_client
    await _to_qa(admin, rig["release"].id)
    resp = await admin.post(f"/releases/{rig['release'].id}/ship", json={})
    assert resp.status_code == 422
    assert (await _release(admin, rig["release"].id))["status"] == "qa"


@pytest.mark.asyncio
@pytest.mark.parametrize("role,lead,ok", [
    ("cto", False, True), ("admin", False, True), ("product_manager", False, False),
    ("developer", False, False), ("qa", False, False),
    ("qa", True, True), ("developer", True, True),
])
async def test_who_can_ship(factories, client_for, role, lead, ok):
    user = await factories.user(role=role)
    project = await factories.project(triage_lead_id=user.id if lead else None)
    release = await factories.release(project_id=project.id)
    await _to_qa(factories.admin_client, release.id)
    c = await client_for(user)
    resp = await c.post(f"/releases/{release.id}/ship", json={"confirm": True})
    assert (resp.status_code == 200) == ok, resp.text
    if not ok:
        assert resp.status_code == 403


@pytest.mark.asyncio
async def test_shipped_release_is_read_only(factories, rig):
    admin = factories.admin_client
    rid = rig["release"].id
    await _to_qa(admin, rid)
    await admin.post(f"/releases/{rid}/ship", json={"confirm": True})
    body = await _release(admin, rid)
    assert body["allowed_transitions"] == []
    assert body["allowed_actions"] == []
    for resp in (
        await admin.patch(f"/releases/{rid}", json={"description": "late edit"}),
        await admin.post(f"/releases/{rid}/status", json={"to": "development"}),
        await admin.post(f"/releases/{rid}/go-nogo", json={"decision": "blocked"}),
        await admin.post(f"/releases/{rid}/cancel"),
        await admin.delete(f"/releases/{rid}"),
    ):
        assert resp.status_code == 409, resp.text
        assert resp.json()["code"] == "release_final"


@pytest.mark.asyncio
async def test_ship_notifies_item_assignees_and_the_cto(factories, client_for, rig):
    dev = await factories.user(role="developer")
    cto = await factories.user(role="cto")
    bystander = await factories.user(role="developer")
    await _item(factories, rig["release"].id, rig["project"].id, "done", assignee_id=dev.id)
    await _to_qa(factories.admin_client, rig["release"].id)
    await factories.admin_client.post(f"/releases/{rig['release'].id}/ship", json={"confirm": True})

    for user, expected in ((dev, 1), (cto, 1), (bystander, 0)):
        inbox = (await (await client_for(user)).get(
            "/inbox", params={"event_type": "release_shipped"},
        )).json()
        assert inbox["total"] == expected, (user.role, inbox)


# ── Activity (FR-51) ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activity_records_lifecycle_dates_items_go_nogo_and_ship(factories, rig):
    admin = factories.admin_client
    rid, pid = rig["release"].id, rig["project"].id
    await _set_target(admin, rid, datetime(2031, 1, 1, tzinfo=UTC))
    it = await _item(factories, rid, pid, "todo")
    other = await factories.issue(project_id=pid, type="task")
    await admin.patch(f"/issues/{other.id}", json={"release_id": rid})
    await admin.patch(f"/issues/{other.id}", json={"release_id": None})
    await _to_qa(admin, rid)
    await admin.post(f"/releases/{rid}/go-nogo", json={"decision": "blocked", "note": "crash"})
    await admin.post(f"/releases/{rid}/ship", json={"confirm": True})

    resp = await admin.get(f"/releases/{rid}/activity")
    assert resp.status_code == 200, resp.text
    events = resp.json()["events"]
    types = [e["event_type"] for e in events]
    for expected in (
        "dates_changed", "item_added", "item_removed", "status_changed", "go_nogo", "shipped",
    ):
        assert expected in types, types
    added = [e for e in events if e["event_type"] == "item_added"]
    assert {e["meta"]["issue_id"] for e in added} == {it.id, other.id}
    # The ship is one event, not a status change plus a ship.
    assert not any(
        e["event_type"] == "status_changed" and e["meta"]["to"] == "released" for e in events
    )
    shipped = next(e for e in events if e["event_type"] == "shipped")
    assert shipped["meta"]["moved"] == 1
    # The ship's removals are recorded too.
    removed_by_ship = [
        e for e in events
        if e["event_type"] == "item_removed" and e["meta"].get("reason") == "ship"
    ]
    assert [e["meta"]["issue_id"] for e in removed_by_ship] == [it.id]


@pytest.mark.asyncio
async def test_item_removed_writes_release_changed_on_the_item(factories, rig):
    admin = factories.admin_client
    it = await _item(factories, rig["release"].id, rig["project"].id, "todo")
    await _to_qa(admin, rig["release"].id)
    await admin.post(f"/releases/{rig['release'].id}/ship", json={"confirm": True})
    events = (await admin.get(f"/issues/{it.id}/timeline")).json()["items"]
    assert any(e["event_type"] == "release_changed" for e in events)


# ── Board, items, Stream (FR-47, FR-51) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_release_board_and_items(factories, rig):
    admin = factories.admin_client
    rid, pid = rig["release"].id, rig["project"].id
    old_done = await _item(factories, rid, pid, "done")
    await _backdate_completed(old_done.id, datetime.now(UTC) - timedelta(days=400))
    todo = await _item(factories, rid, pid, "todo")
    await _item(factories, rid, pid, "cancelled")

    board = (await admin.get(f"/releases/{rid}/board")).json()
    cols = {c["status"]: [i["id"] for i in c["items"]] for c in board["columns"]}
    assert list(cols) == [
        "todo", "rejected", "in_progress", "to_review", "in_review", "blocked", "done",
    ]
    assert cols["todo"] == [todo.id]
    # A release's Done column is unbounded by default.
    assert cols["done"] == [old_done.id]
    assert board["done_from"] is None

    items = (await admin.get(f"/releases/{rid}/items")).json()
    assert items["total"] == 3


@pytest.mark.asyncio
async def test_ac_63_stream_done_column_default_7_days_and_range(factories, rig, clock):
    admin = factories.admin_client
    sid, pid = rig["stream_id"], rig["project"].id
    now = datetime.now(UTC)
    clock.set(now)
    recent = await _item(factories, sid, pid, "done")
    await _backdate_completed(recent.id, now - timedelta(days=2))
    month = await _item(factories, sid, pid, "done")
    await _backdate_completed(month.id, now - timedelta(days=20))
    ancient = await _item(factories, sid, pid, "done")
    await _backdate_completed(ancient.id, now - timedelta(days=200))
    open_old = await _item(factories, sid, pid, "in_progress")

    async def done_ids(**params):
        resp = await admin.get(f"/releases/{sid}/board", params=params)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        cols = {c["status"]: [i["id"] for i in c["items"]] for c in body["columns"]}
        assert open_old.id in cols["in_progress"]  # open columns are never filtered
        return set(cols["done"]), body

    ids, body = await done_ids()
    assert ids == {recent.id}
    assert body["done_from"] is not None

    ids, _ = await done_ids(done_from=(now - timedelta(days=30)).isoformat())
    assert ids == {recent.id, month.id}

    ids, _ = await done_ids(
        done_from=(now - timedelta(days=250)).isoformat(),
        done_to=(now - timedelta(days=10)).isoformat(),
    )
    assert ids == {month.id, ancient.id}

    stream = (await admin.get(f"/projects/{pid}/stream")).json()
    assert stream["id"] == sid and stream["kind"] == "stream"
    assert stream["allowed_transitions"] == [] and stream["allowed_actions"] == []


# ── Overdue notification (§13) ───────────────────────────────────────────────


async def _run_overdue(now):
    from app.tasks.releases import run_overdue_check

    return await run_overdue_check(now)


async def _overdue_count(client):
    inbox = (await client.get("/inbox", params={"event_type": "release_overdue"})).json()
    return inbox["total"], inbox["items"]


@pytest.mark.asyncio
async def test_overdue_job_notifies_ctos_once_and_again_after_a_new_date(
    factories, client_for, rig, telegram,
):
    admin = factories.admin_client
    cto = await factories.user(role="cto")
    dev = await factories.user(role="developer")
    await telegram.link_telegram(cto)
    cto_c, dev_c = await client_for(cto), await client_for(dev)
    rid = rig["release"].id
    now = datetime(2030, 6, 1, 9, tzinfo=UTC)
    await _set_target(admin, rid, now - timedelta(days=1))

    await _run_overdue(now)
    await _run_overdue(now)
    total, items = await _overdue_count(cto_c)
    assert total == 1
    assert (await _overdue_count(dev_c))[0] == 0
    assert [t for t, _ in telegram.sent_to(cto)] == ["release_overdue"]

    # Moving the date later clears the notice; slipping again notifies again.
    await _set_target(admin, rid, now + timedelta(days=3))
    await _run_overdue(now)
    assert (await _overdue_count(cto_c))[0] == 1
    await _run_overdue(now + timedelta(days=5))
    assert (await _overdue_count(cto_c))[0] == 2


@pytest.mark.asyncio
async def test_overdue_job_skips_released_cancelled_and_undated(factories, client_for, rig):
    admin = factories.admin_client
    cto = await factories.user(role="cto")
    pid = rig["project"].id
    now = datetime(2030, 6, 1, tzinfo=UTC)
    shipped = rig["release"]
    cancelled = await factories.release(project_id=pid)
    await factories.release(project_id=pid)  # no target date
    for r in (shipped, cancelled):
        await _set_target(admin, r.id, now - timedelta(days=3))
    await _to_qa(admin, shipped.id)
    await admin.post(f"/releases/{shipped.id}/ship", json={"confirm": True})
    await admin.post(f"/releases/{cancelled.id}/cancel")

    await _run_overdue(now)
    assert (await _overdue_count(await client_for(cto)))[0] == 0


@pytest.mark.asyncio
async def test_inbox_renders_a_release_only_item(factories, client_for, rig):
    admin = factories.admin_client
    cto = await factories.user(role="cto")
    now = datetime(2030, 6, 1, tzinfo=UTC)
    await _set_target(admin, rig["release"].id, now - timedelta(days=1))
    await _run_overdue(now)
    total, items = await _overdue_count(await client_for(cto))
    assert total == 1
    item = items[0]
    assert item["issueId"] is None and item["issueTitle"] is None
    assert item["release"]["id"] == rig["release"].id
    assert item["release"]["version"] == rig["release"].version
    assert item["release"]["projectId"] == rig["project"].id


# ── Keeps working for dates set as plain dates ───────────────────────────────


@pytest.mark.asyncio
async def test_changing_target_date_clears_overdue_notice_date_only(factories, rig):
    admin = factories.admin_client
    resp = await admin.patch(
        f"/releases/{rig['release'].id}", json={"code_freeze_date": date(2031, 1, 1).isoformat()},
    )
    assert resp.status_code == 200
    events = (await admin.get(f"/releases/{rig['release'].id}/activity")).json()["events"]
    assert events[-1]["event_type"] == "dates_changed"
    assert "code_freeze_date" in events[-1]["meta"]["changes"]


# ── Activity starts at creation; every lifecycle move is recorded ────────────


@pytest.mark.asyncio
async def test_activity_starts_with_created_then_each_lifecycle_move(factories, client_for, rig):
    admin = factories.admin_client
    resp = await admin.post(f"/projects/{rig['project'].id}/releases", json={"version": "4.0.0"})
    assert resp.status_code == 201, resp.text
    rid = resp.json()["id"]

    await _to_qa(admin, rid)
    # Admin can take a release in QA back to Development (FR-50).
    back = await admin.post(f"/releases/{rid}/status", json={"to": "development"})
    assert back.status_code == 200, back.text
    assert back.json()["status"] == "development"
    assert "qa" in back.json()["allowed_transitions"]

    events = (await admin.get(f"/releases/{rid}/activity")).json()["events"]
    # Oldest first (A → Z).
    oldest_first = [(e["event_type"], e["meta"].get("from"), e["meta"].get("to")) for e in events]
    assert oldest_first == [
        ("created", None, None),
        ("status_changed", "planning", "development"),
        ("status_changed", "development", "qa"),
        ("status_changed", "qa", "development"),
    ]
    created = events[0]
    assert created["meta"] == {"version": "4.0.0", "status": "planning"}
    stamps = [e["created_at"] for e in events]
    assert stamps == sorted(stamps)
    assert created["actor"]["id"] == factories.admin_id


@pytest.mark.asyncio
async def test_qa_back_to_development_is_offered_to_admin_in_qa(factories, rig):
    admin = factories.admin_client
    body = await _to_qa(admin, rig["release"].id)
    assert "development" in body["allowed_transitions"]


@pytest.mark.asyncio
async def test_stream_items_share_the_done_range_with_the_board(factories, rig, clock):
    admin = factories.admin_client
    sid, pid = rig["stream_id"], rig["project"].id
    now = datetime.now(UTC)
    clock.set(now)
    recent = await _item(factories, sid, pid, "done")
    await _backdate_completed(recent.id, now - timedelta(days=2))
    old = await _item(factories, sid, pid, "done")
    await _backdate_completed(old.id, now - timedelta(days=60))
    open_item = await _item(factories, sid, pid, "in_progress")
    dropped = await _item(factories, sid, pid, "cancelled")

    async def item_ids(**params):
        resp = await admin.get(f"/releases/{sid}/items", params=params)
        assert resp.status_code == 200, resp.text
        return {i["id"] for i in resp.json()["items"]}, resp.json()

    # Default: Done bounded to the last 7 days; everything else always listed.
    ids, body = await item_ids()
    assert ids == {recent.id, open_item.id, dropped.id}
    assert body["done_from"] is not None and body["done_to"] is None

    ids, _ = await item_ids(done_from=(now - timedelta(days=90)).isoformat())
    assert ids == {recent.id, old.id, open_item.id, dropped.id}

    ids, _ = await item_ids(
        done_from=(now - timedelta(days=90)).isoformat(),
        done_to=(now - timedelta(days=30)).isoformat(),
    )
    assert ids == {old.id, open_item.id, dropped.id}

    # The board and the items agree on Done for the same range.
    board = (await admin.get(f"/releases/{sid}/board", params={
        "done_from": (now - timedelta(days=90)).isoformat(),
        "done_to": (now - timedelta(days=30)).isoformat(),
    })).json()
    done_col = next(c for c in board["columns"] if c["status"] == "done")
    assert {i["id"] for i in done_col["items"]} == {old.id}


@pytest.mark.asyncio
async def test_issue_response_names_its_container(factories, rig):
    admin = factories.admin_client
    pid = rig["project"].id
    in_release = await factories.issue(project_id=pid, release_id=rig["release"].id, type="task")
    in_stream = await factories.issue(project_id=pid, release_id=rig["stream_id"])  # a bug
    in_backlog = await factories.issue(project_id=pid, type="task")

    r = (await admin.get(f"/issues/{in_release.id}")).json()
    assert (r["container_kind"], r["release_version"], r["release_status"]) == (
        "release", rig["release"].version, "planning",
    )
    s = (await admin.get(f"/issues/{in_stream.id}")).json()
    assert (s["type"], s["container_kind"], s["release_status"]) == ("bug", "stream", None)
    b = (await admin.get(f"/issues/{in_backlog.id}")).json()
    assert (b["container_kind"], b["release_id"]) == (None, None)
    assert r["project_slug"] == s["project_slug"] == b["project_slug"] == rig["project"].slug
