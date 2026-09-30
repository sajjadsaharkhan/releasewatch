"""Slice 10 — personal queue and board.

docs/phase-2/10-personal-queue.md (PRD v3 FR-33–FR-42, FR-63/64, BR-38–BR-46,
BR-61; AC-32–AC-44, AC-74, AC-75; §13 due-date notices). Ordering is proven
through ``GET /users/{id}/queue``; the pure rules are in ``test_queue_order.py``.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db.session import get_engine

# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def rig(factories, client_for):
    dev = await factories.user(role="developer")
    project = await factories.project()
    stream_id = await factories.stream_id(project_id=project.id)
    return {
        "project": project, "stream_id": stream_id,
        "dev": dev, "dev_client": await client_for(dev),
    }


async def _task(factories, rig, priority="medium", assignee=None, **fields):
    """A To do task in the Stream, assigned to the rig's developer by default."""
    return await factories.issue(
        project_id=rig["project"].id, release_id=rig["stream_id"], type="task",
        priority=priority, assignee_id=(assignee or rig["dev"]).id, **fields,
    )


async def _queue(client, owner="me"):
    resp = await client.get(f"/users/{owner}/queue")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _order(client, owner="me"):
    """``(pinned ids, rest ids)`` in queue order."""
    q = await _queue(client, owner)
    return (
        [e["issue"]["id"] for e in q["groups"]["pinned"]],
        [e["issue"]["id"] for e in q["groups"]["rest"]],
    )


async def _flat(client, owner="me"):
    pinned, rest = await _order(client, owner)
    return pinned + rest


async def _pin(client, issue_id, owner="me"):
    return await client.post(f"/users/{owner}/queue/pins", json={"issue_id": issue_id})


async def _unpin(client, issue_id, owner="me"):
    return await client.delete(f"/users/{owner}/queue/pins/{issue_id}")


async def _move(client, issue_id, owner="me", **anchor):
    return await client.post(f"/users/{owner}/queue/move", json={"issue_id": issue_id, **anchor})


async def _transition(client, issue_id, to):
    resp = await client.post(f"/issues/{issue_id}/transition", json={"to": to})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _timeline_total(client, issue_id):
    resp = await client.get(f"/issues/{issue_id}/timeline", params={"size": 50})
    return resp.json()["total"]


async def _inbox(client, event_type=None):
    params = {"size": 50, **({"event_type": event_type} if event_type else {})}
    return (await client.get("/inbox", params=params)).json()["items"]


# ── Membership (BR-38) ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_queue_holds_only_open_board_items_across_projects(factories, rig):
    admin = factories.admin_client
    other = await factories.project()
    other_stream = await factories.stream_id(project_id=other.id)
    a = await _task(factories, rig)
    b = await factories.issue(
        project_id=other.id, release_id=other_stream, type="task", priority="medium",
        assignee_id=rig["dev"].id,
    )
    done = await _task(factories, rig)
    await _transition(admin, done.id, "done")
    cancelled = await _task(factories, rig)
    await _transition(admin, cancelled.id, "cancelled")
    # A bug still in triage (New) isn't committed work.
    await factories.issue(
        project_id=rig["project"].id, release_id=rig["stream_id"], assignee_id=rig["dev"].id,
    )

    assert set(await _flat(rig["dev_client"])) == {a.id, b.id}


@pytest.mark.asyncio
async def test_new_task_enters_by_default_rule(factories, rig):
    low = await _task(factories, rig, "low")
    high = await _task(factories, rig, "high")
    medium = await _task(factories, rig, "medium")
    assert await _flat(rig["dev_client"]) == [high.id, medium.id, low.id]


# ── Default rule (FR-37, FR-39) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_35_new_high_bug_inserted_above_first_lower_ranked(factories, rig):
    dev_c = rig["dev_client"]
    low = await _task(factories, rig, "low")
    critical = await _task(factories, rig, "critical")
    medium = await _task(factories, rig, "medium")
    # A manual order that isn't the default one: low, critical, medium.
    assert (await _move(dev_c, low.id, before_id=critical.id)).status_code == 200
    assert await _flat(dev_c) == [low.id, critical.id, medium.id]

    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["stream_id"])
    resp = await factories.admin_client.post(
        f"/issues/{bug.id}/triage",
        json={"outcome": "accept", "priority": "high", "assignee_id": rig["dev"].id},
    )
    assert resp.status_code == 200, resp.text
    # Directly above the first item that ranks lower than High — the Low one.
    assert await _flat(dev_c) == [bug.id, low.id, critical.id, medium.id]


@pytest.mark.asyncio
async def test_ac_36_new_critical_below_pins_above_lower_priority(factories, rig):
    dev_c = rig["dev_client"]
    pinned_low = await _task(factories, rig, "low")
    high = await _task(factories, rig, "high")
    assert (await _pin(dev_c, pinned_low.id)).status_code == 200

    critical = await _task(factories, rig, "critical")
    assert await _order(dev_c) == ([pinned_low.id], [critical.id, high.id])


@pytest.mark.asyncio
async def test_task_p2_ranks_above_bug_medium(factories, rig):
    medium_bug = await factories.issue(project_id=rig["project"].id, release_id=rig["stream_id"])
    await factories.admin_client.post(
        f"/issues/{medium_bug.id}/triage",
        json={"outcome": "accept", "priority": "medium", "assignee_id": rig["dev"].id},
    )
    high_task = await _task(factories, rig, "high")
    assert await _flat(rig["dev_client"]) == [high_task.id, medium_bug.id]


@pytest.mark.asyncio
async def test_due_date_then_age_break_priority_ties(factories, rig):
    older = await _task(factories, rig)
    undated = await _task(factories, rig)
    dated = await _task(factories, rig, due_date=(date.today() + timedelta(days=30)).isoformat())
    assert await _flat(rig["dev_client"]) == [dated.id, older.id, undated.id]


@pytest.mark.asyncio
async def test_priority_change_reinserts_unpinned_by_default_rule(factories, rig):
    dev_c = rig["dev_client"]
    a = await _task(factories, rig, "high")
    b = await _task(factories, rig, "medium")
    resp = await factories.admin_client.patch(f"/issues/{b.id}", json={"priority": "critical"})
    assert resp.status_code == 200, resp.text
    assert await _flat(dev_c) == [b.id, a.id]


@pytest.mark.asyncio
async def test_pinned_item_whose_priority_changes_stays_pinned_in_place(factories, rig):
    dev_c = rig["dev_client"]
    a = await _task(factories, rig, "low")
    b = await _task(factories, rig, "low")
    await _pin(dev_c, a.id)
    await _pin(dev_c, b.id)
    await factories.admin_client.patch(f"/issues/{b.id}", json={"priority": "critical"})
    assert await _order(dev_c) == ([a.id, b.id], [])


# ── Reorder (FR-38) ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_drag_rest_into_pins_is_refused(factories, rig):
    dev_c = rig["dev_client"]
    a = await _task(factories, rig)
    b = await _task(factories, rig)
    await _pin(dev_c, a.id)
    resp = await _move(dev_c, b.id, before_id=a.id)
    assert resp.status_code == 409
    assert resp.json()["code"] == "queue_group_boundary"
    assert "Pin" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_reorder_within_pins(factories, rig):
    dev_c = rig["dev_client"]
    a, b = await _task(factories, rig), await _task(factories, rig)
    await _pin(dev_c, a.id)
    await _pin(dev_c, b.id)
    assert (await _move(dev_c, b.id, before_id=a.id)).status_code == 200
    assert await _order(dev_c) == ([b.id, a.id], [])


# ── Pins (FR-40, BR-40, BR-41) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_32_fifth_pin_refused_names_limit(factories, rig):
    dev_c = rig["dev_client"]
    items = [await _task(factories, rig) for _ in range(5)]
    for item in items[:4]:
        assert (await _pin(dev_c, item.id)).status_code == 200
    resp = await _pin(dev_c, items[4].id)
    assert resp.status_code == 409
    assert resp.json()["code"] == "pin_limit_reached"
    assert "4" in resp.json()["detail"]
    q = await _queue(dev_c)
    assert (q["pins_used"], q["pin_limit"]) == (4, 4)


@pytest.mark.asyncio
async def test_ac_33_cto_pin_locked_owner_cannot_unpin_and_is_notified(factories, client_for, rig):
    dev, dev_c = rig["dev"], rig["dev_client"]
    cto = await factories.user(role="cto")
    cto_c = await client_for(cto)
    item = await _task(factories, rig)
    other = await _task(factories, rig)

    resp = await _pin(cto_c, item.id, owner=dev.id)
    assert resp.status_code == 200, resp.text
    entry = (await _queue(dev_c))["groups"]["pinned"][0]
    assert entry["pin_locked"] is True
    assert entry["pinned_by"]["id"] == cto.id
    assert entry["issue"]["pin_locked"] is True

    resp = await _unpin(dev_c, item.id)
    assert resp.status_code == 409
    assert resp.json()["code"] == "pin_locked"

    notices = await _inbox(dev_c, "queue_changed")
    assert len(notices) == 1
    assert notices[0]["meta"] == {"action": "pin", "old_index": 1, "new_index": 1}

    # The owner's own pin isn't locked, and pinning your own queue notifies no one.
    await _pin(dev_c, other.id)
    pinned = (await _queue(dev_c))["groups"]["pinned"]
    assert [p["pin_locked"] for p in pinned] == [True, False]
    assert len(await _inbox(dev_c, "queue_changed")) == 1

    # The CTO can remove their own locked pin.
    assert (await _unpin(cto_c, item.id, owner=dev.id)).status_code == 200


@pytest.mark.asyncio
async def test_cto_pinning_own_queue_is_not_locked(factories, client_for, rig):
    cto = await factories.user(role="cto")
    cto_c = await client_for(cto)
    item = await _task(factories, rig, assignee=cto)
    await _pin(cto_c, item.id)
    assert (await _queue(cto_c))["groups"]["pinned"][0]["pin_locked"] is False
    assert (await _unpin(cto_c, item.id)).status_code == 200


@pytest.mark.asyncio
async def test_ac_34_cto_pin_refused_at_limit(factories, client_for, rig):
    dev, dev_c = rig["dev"], rig["dev_client"]
    cto_c = await client_for(await factories.user(role="cto"))
    items = [await _task(factories, rig) for _ in range(5)]
    for item in items[:4]:
        await _pin(dev_c, item.id)
    resp = await _pin(cto_c, items[4].id, owner=dev.id)
    assert resp.status_code == 409
    assert resp.json()["code"] == "pin_limit_reached"
    assert "Unpin one first" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_unpinning_reinserts_by_default_rule(factories, rig):
    dev_c = rig["dev_client"]
    low = await _task(factories, rig, "low")
    high = await _task(factories, rig, "high")
    medium = await _task(factories, rig, "medium")
    await _pin(dev_c, low.id)
    await _move(dev_c, medium.id, before_id=high.id)
    assert await _order(dev_c) == ([low.id], [medium.id, high.id])
    await _unpin(dev_c, low.id)
    assert await _order(dev_c) == ([], [medium.id, high.id, low.id])


@pytest.mark.asyncio
async def test_pin_not_in_queue(factories, rig):
    someone = await factories.user(role="developer")
    theirs = await _task(factories, rig, assignee=someone)
    resp = await _pin(rig["dev_client"], theirs.id)
    assert resp.status_code == 404
    assert resp.json()["code"] == "not_in_queue"


# ── Who may act (BR-42, AC-40) ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_40_pm_and_triage_lead_cannot_reorder_or_pin(factories, client_for, rig):
    dev = rig["dev"]
    a, b = await _task(factories, rig), await _task(factories, rig)
    pm = await factories.user(role="pm")
    lead = await factories.user(role="developer")
    await factories.admin_client.patch(
        f"/projects/{rig['project'].id}", json={"triage_lead_id": lead.id},
    )
    for user in (pm, lead):
        client = await client_for(user)
        for resp in (
            await client.get(f"/users/{dev.id}/queue"),
            await _move(client, b.id, owner=dev.id, before_id=a.id),
            await _pin(client, a.id, owner=dev.id),
            await _unpin(client, a.id, owner=dev.id),
            await client.get(f"/users/{dev.id}/queue/history"),
        ):
            assert resp.status_code == 403, resp.text
    # Their own queue is theirs to order.
    q = await _queue(await client_for(pm))
    assert (q["can_reorder"], q["can_pin"]) == (True, True)


@pytest.mark.asyncio
async def test_cto_and_admin_can_reorder_anyones_queue(factories, client_for, rig):
    dev = rig["dev"]
    a, b = await _task(factories, rig), await _task(factories, rig)
    cto_c = await client_for(await factories.user(role="cto"))
    q = await _queue(cto_c, dev.id)
    assert (q["can_reorder"], q["can_pin"]) == (True, True)
    assert (await _move(cto_c, b.id, owner=dev.id, before_id=a.id)).status_code == 200
    resp = await _move(factories.admin_client, a.id, owner=dev.id, before_id=b.id)
    assert resp.status_code == 200
    assert await _flat(rig["dev_client"]) == [a.id, b.id]


@pytest.mark.asyncio
async def test_support_has_no_queue(factories, client_for, rig):
    support = await factories.user(role="support")
    resp = await (await client_for(support)).get("/users/me/queue")
    assert resp.status_code == 404


# ── History (FR-41, BR-44) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_37_cto_reorder_in_history_not_in_timeline(factories, client_for, rig):
    dev, dev_c = rig["dev"], rig["dev_client"]
    cto = await factories.user(role="cto")
    cto_c = await client_for(cto)
    a, b = await _task(factories, rig), await _task(factories, rig)
    timeline_before = await _timeline_total(dev_c, b.id)

    resp = await _move(cto_c, b.id, owner=dev.id, before_id=a.id)
    assert resp.status_code == 200, resp.text

    history = (await dev_c.get("/users/me/queue/history")).json()
    assert history["total"] == 1
    entry = history["items"][0]
    assert entry["action"] == "reorder"
    assert entry["actor"]["id"] == cto.id
    assert entry["issue_id"] == b.id
    assert (entry["old_index"], entry["new_index"]) == (2, 1)
    timeline_after = await _timeline_total(dev_c, b.id)
    assert timeline_after == timeline_before

    # The CTO reads it too; automatic insertions never appear.
    assert (await cto_c.get(f"/users/{dev.id}/queue/history")).json()["total"] == 1
    notices = await _inbox(dev_c, "queue_changed")
    assert [n["meta"]["action"] for n in notices] == ["reorder"]


@pytest.mark.asyncio
async def test_history_has_no_edit_or_delete(factories, rig):
    dev_c = rig["dev_client"]
    assert (await dev_c.delete("/users/me/queue/history")).status_code == 405
    assert (await dev_c.patch("/users/me/queue/history")).status_code == 405


# ── Leaving and returning (BR-45, BR-46, FR-64) ───────────────────────────────


@pytest.mark.asyncio
async def test_ac_38_reassign_releases_pin_and_reinserts(factories, client_for, rig):
    dev_c = rig["dev_client"]
    other = await factories.user(role="developer")
    other_c = await client_for(other)
    low = await _task(factories, rig, "low", assignee=other)
    item = await _task(factories, rig, "high")
    await _pin(dev_c, item.id)

    resp = await factories.admin_client.patch(f"/issues/{item.id}", json={"assignee_id": other.id})
    assert resp.status_code == 200, resp.text
    assert await _flat(dev_c) == []
    assert await _order(other_c) == ([], [item.id, low.id])


@pytest.mark.asyncio
async def test_ac_39_done_releases_pin(factories, rig):
    dev_c = rig["dev_client"]
    items = [await _task(factories, rig) for _ in range(4)]
    for item in items:
        await _pin(dev_c, item.id)
    await _transition(factories.admin_client, items[0].id, "done")
    q = await _queue(dev_c)
    assert q["pins_used"] == 3
    fifth = await _task(factories, rig)
    assert (await _pin(dev_c, fifth.id)).status_code == 200


@pytest.mark.asyncio
async def test_ac_74_returned_item_restores_previous_position(factories, client_for, rig):
    dev_c = rig["dev_client"]
    qa_c = await client_for(await factories.user(role="qa"))
    a, b, c = await _task(factories, rig), await _task(factories, rig), await _task(factories, rig)
    assert await _flat(dev_c) == [a.id, b.id, c.id]
    await _transition(factories.admin_client, b.id, "done")
    assert await _flat(dev_c) == [a.id, c.id]

    resp = await qa_c.post(f"/issues/{b.id}/reject", json={"comment": "Still broken on prod."})
    assert resp.status_code == 200, resp.text
    assert await _flat(dev_c) == [a.id, b.id, c.id]


@pytest.mark.asyncio
async def test_ac_75_returned_item_never_above_pins(factories, client_for, rig):
    dev_c = rig["dev_client"]
    qa_c = await client_for(await factories.user(role="qa"))
    first = await _task(factories, rig, "critical")
    other = await _task(factories, rig, "low")
    await _pin(dev_c, first.id)
    await _transition(factories.admin_client, first.id, "done")
    # Pins added meanwhile.
    await _pin(dev_c, other.id)

    await qa_c.post(f"/issues/{first.id}/reject", json={"comment": "Regressed."})
    assert await _order(dev_c) == ([other.id], [first.id])
    later = await _task(factories, rig, "low")
    assert await _order(dev_c) == ([other.id], [first.id, later.id])


@pytest.mark.asyncio
async def test_reject_from_review_keeps_queue_order(factories, client_for, rig):
    dev_c = rig["dev_client"]
    qa_c = await client_for(await factories.user(role="qa"))
    a, b, c = await _task(factories, rig), await _task(factories, rig), await _task(factories, rig)
    await _move(dev_c, c.id, before_id=a.id)
    before = await _flat(dev_c)
    await _transition(factories.admin_client, b.id, "in_review")
    resp = await qa_c.post(f"/issues/{b.id}/reject", json={"comment": "Nope."})
    assert resp.status_code == 200, resp.text
    assert await _flat(dev_c) == before


@pytest.mark.asyncio
async def test_dormant_entry_is_hidden_and_not_counted(factories, rig):
    dev_c = rig["dev_client"]
    item = await _task(factories, rig)
    await _pin(dev_c, item.id)
    await _transition(factories.admin_client, item.id, "done")
    q = await _queue(dev_c)
    assert q["groups"] == {"pinned": [], "rest": []}
    assert q["pins_used"] == 0
    board = (await dev_c.get("/users/me/board")).json()
    open_ids = [
        i["id"] for col in board["columns"] if col["status"] != "done" for i in col["items"]
    ]
    assert open_ids == []
    done = next(col for col in board["columns"] if col["status"] == "done")
    assert [i["id"] for i in done["items"]] == [item.id]
    assert done["items"][0]["pinned"] is False


@pytest.mark.asyncio
async def test_ship_keeps_assigned_entry_and_pin(factories, rig):
    dev_c = rig["dev_client"]
    release = await factories.release(project_id=rig["project"].id)
    item = await factories.issue(
        project_id=rig["project"].id, release_id=release.id, type="task", priority="medium",
        assignee_id=rig["dev"].id,
    )
    await _transition(factories.admin_client, item.id, "in_progress")
    await _pin(dev_c, item.id)
    await factories.set_release_status(release.id, "released")

    issue = (await dev_c.get(f"/issues/{item.id}")).json()
    assert issue["release_id"] is None
    assert await _order(dev_c) == ([item.id], [])


@pytest.mark.asyncio
async def test_deleted_item_leaves_queue(factories, rig):
    item = await _task(factories, rig)
    assert (await factories.admin_client.delete(f"/issues/{item.id}")).status_code == 204
    assert await _flat(rig["dev_client"]) == []
    assert (await factories.admin_client.post(f"/issues/{item.id}/restore")).status_code == 204
    assert await _flat(rig["dev_client"]) == [item.id]


# ── Board (FR-34, FR-35, AC-41, AC-42) ────────────────────────────────────────


async def _backdate_completed(issue_id: int, when: datetime) -> None:
    """No endpoint sets when an item was completed — bootstrap it directly."""
    async with get_engine().begin() as conn:
        await conn.execute(
            text("UPDATE issues SET completed_at = :w WHERE id = :i"), {"w": when, "i": issue_id},
        )


@pytest.mark.asyncio
async def test_board_column_order_equals_queue_order(factories, client_for, rig):
    dev_c = rig["dev_client"]
    qa_c = await client_for(await factories.user(role="qa"))
    items = [await _task(factories, rig) for _ in range(5)]
    await _transition(factories.admin_client, items[1].id, "in_progress")
    await _transition(factories.admin_client, items[4].id, "in_review")
    await qa_c.post(f"/issues/{items[4].id}/reject", json={"comment": "Again."})
    await _move(dev_c, items[3].id, before_id=items[0].id)
    await _pin(dev_c, items[2].id)

    queue = await _flat(dev_c)
    board = (await dev_c.get("/users/me/board")).json()
    columns = {c["status"]: [i["id"] for i in c["items"]] for c in board["columns"]}
    assert list(columns) == [
        "todo", "rejected", "in_progress", "to_review", "in_review", "done", "blocked",
    ]
    statuses = {i.id: "todo" for i in items} | {items[1].id: "in_progress", items[4].id: "rejected"}
    for status in ("todo", "rejected", "in_progress"):
        assert columns[status] == [i for i in queue if statuses[i] == status]
    assert columns["rejected"] == [items[4].id]


@pytest.mark.asyncio
async def test_ac_42_done_column_excludes_items_older_than_7_days(factories, rig, clock):
    now = datetime(2030, 3, 10, 12, tzinfo=UTC)
    clock.set(now)
    old, recent = await _task(factories, rig), await _task(factories, rig)
    for item in (old, recent):
        await _transition(factories.admin_client, item.id, "done")
    await _backdate_completed(old.id, now - timedelta(days=8))
    await _backdate_completed(recent.id, now - timedelta(days=1))

    board = (await rig["dev_client"].get("/users/me/board")).json()
    done = next(c for c in board["columns"] if c["status"] == "done")
    assert [i["id"] for i in done["items"]] == [recent.id]
    board = (await rig["dev_client"].get("/users/me/board", params={"done_days": 30})).json()
    done = next(c for c in board["columns"] if c["status"] == "done")
    assert [i["id"] for i in done["items"]] == [recent.id, old.id]


# ── Cards (FR-42, AC-43, AC-44) ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_43_card_default_fields_only(factories, rig):
    item = await _task(factories, rig)
    card = (await _queue(rig["dev_client"]))["groups"]["rest"][0]["issue"]
    assert card["id"] == item.id
    assert card["title"] == item.title
    assert card["project"]["slug"] == rig["project"].slug
    assert card["priority"] == "medium"
    assert card["key"].startswith("TASK-")
    # Signals are empty for a plain item.
    assert card["recurrence_count"] == 1
    assert card["due_date"] is None and card["due_state"] == "none"
    assert card["is_tech_debt"] is False
    assert card["pinned"] is False and card["pin_locked"] is False
    assert card["cycle_number"] == 1
    assert card["reject_reason"] is None
    # Hover fields.
    assert card["container"] == {"kind": "stream", "name": "Stream"}


@pytest.mark.asyncio
async def test_ac_44_overdue_due_state(factories, rig, clock):
    today = date(2030, 5, 20)
    clock.set(datetime(2030, 5, 20, 9, tzinfo=UTC))
    overdue = await _task(factories, rig, due_date=(today - timedelta(days=1)).isoformat())
    soon = await _task(factories, rig, due_date=(today + timedelta(days=2)).isoformat())
    later = await _task(factories, rig, due_date=(today + timedelta(days=3)).isoformat())
    cards = {
        e["issue"]["id"]: e["issue"]["due_state"]
        for e in (await _queue(rig["dev_client"]))["groups"]["rest"]
    }
    assert cards == {overdue.id: "overdue", soon.id: "soon", later.id: "none"}


@pytest.mark.asyncio
async def test_rejected_card_carries_reason_and_cycle(factories, client_for, rig):
    qa_c = await client_for(await factories.user(role="qa"))
    item = await _task(factories, rig)
    await _transition(factories.admin_client, item.id, "in_review")
    await qa_c.post(f"/issues/{item.id}/reject", json={"comment": "Try again."})
    card = (await _queue(rig["dev_client"]))["groups"]["rest"][0]["issue"]
    assert card["status"] == "rejected"
    assert card["reject_reason"] == "review"
    assert card["cycle_number"] == 2
    assert card["reject_comment_id"] is not None


# ── Due-date notices (§13) ────────────────────────────────────────────────────


async def _run_due(now):
    from app.tasks.queue import notify_due_items

    return await notify_due_items(now)


@pytest.mark.asyncio
async def test_due_job_sends_one_due_soon_and_one_overdue(factories, rig, telegram):
    dev, dev_c = rig["dev"], rig["dev_client"]
    await telegram.link_telegram(dev)
    now = datetime(2030, 7, 1, 8, tzinfo=UTC)
    item = await _task(factories, rig, due_date="2030-07-01")

    await _run_due(now)
    await _run_due(now + timedelta(hours=1))
    assert len(await _inbox(dev_c, "due_soon")) == 1
    assert await _inbox(dev_c, "overdue") == []

    await _run_due(now + timedelta(days=1))
    await _run_due(now + timedelta(days=2))
    assert len(await _inbox(dev_c, "due_soon")) == 1
    assert len(await _inbox(dev_c, "overdue")) == 1
    assert [t for t, _ in telegram.sent_to(dev)] == ["due_soon", "overdue"]

    # A new due date resets both notices.
    resp = await factories.admin_client.patch(f"/issues/{item.id}", json={"due_date": "2030-07-05"})
    assert resp.status_code == 200, resp.text
    await _run_due(datetime(2030, 7, 5, 8, tzinfo=UTC))
    await _run_due(datetime(2030, 7, 6, 8, tzinfo=UTC))
    assert len(await _inbox(dev_c, "due_soon")) == 2
    assert len(await _inbox(dev_c, "overdue")) == 2


@pytest.mark.asyncio
async def test_due_job_skips_done_and_unassigned(factories, rig):
    now = datetime(2030, 7, 1, 8, tzinfo=UTC)
    done = await _task(factories, rig, due_date="2030-06-01")
    await _transition(factories.admin_client, done.id, "done")
    await factories.issue(
        project_id=rig["project"].id, release_id=rig["stream_id"], type="task",
        priority="medium", due_date="2030-06-01",
    )
    notified = await _run_due(now)
    assert notified == {"due_soon": [], "overdue": []}


# ── Round 2 of the My Work page (2026-10-01): card fields, Done range, history filters ─


@pytest.mark.asyncio
async def test_card_carries_release_blocker_and_cycle_count(factories, client_for, rig):
    admin = factories.admin_client
    qa_c = await client_for(await factories.user(role="qa"))
    release = await factories.release(project_id=rig["project"].id)
    bug = await factories.issue(
        project_id=rig["project"].id, release_id=release.id, is_release_blocker=True,
    )
    resp = await admin.post(
        f"/issues/{bug.id}/triage",
        json={"outcome": "accept", "priority": "high", "assignee_id": rig["dev"].id},
    )
    assert resp.status_code == 200, resp.text
    await _transition(admin, bug.id, "in_review")
    await qa_c.post(f"/issues/{bug.id}/reject", json={"comment": "Nope."})

    card = (await _queue(rig["dev_client"]))["groups"]["rest"][0]["issue"]
    assert card["is_release_blocker"] is True
    assert card["cycle_count"] == 2
    assert card["container"] == {"kind": "release", "name": release.version}

    plain = await _task(factories, rig)
    rest = (await _queue(rig["dev_client"]))["groups"]["rest"]
    cards = {e["issue"]["id"]: e["issue"] for e in rest}
    assert cards[plain.id]["is_release_blocker"] is False
    assert cards[plain.id]["cycle_count"] == 1


@pytest.mark.asyncio
async def test_board_done_column_takes_an_explicit_range(factories, rig, clock):
    now = datetime(2030, 3, 10, 12, tzinfo=UTC)
    clock.set(now)
    items = [await _task(factories, rig) for _ in range(3)]
    for item in items:
        await _transition(factories.admin_client, item.id, "done")
    await _backdate_completed(items[0].id, now - timedelta(days=20))
    await _backdate_completed(items[1].id, now - timedelta(days=10))
    await _backdate_completed(items[2].id, now - timedelta(days=1))

    async def done_ids(**params):
        board = (await rig["dev_client"].get("/users/me/board", params=params)).json()
        return [i["id"] for c in board["columns"] if c["status"] == "done" for i in c["items"]]

    assert await done_ids() == [items[2].id]
    window = {
        "done_from": (now - timedelta(days=15)).isoformat(),
        "done_to": (now - timedelta(days=5)).isoformat(),
    }
    assert await done_ids(**window) == [items[1].id]
    assert await done_ids(done_from=(now - timedelta(days=30)).isoformat()) == [
        items[2].id, items[1].id, items[0].id,
    ]


async def _history(client, owner="me", **params):
    resp = await client.get(f"/users/{owner}/queue/history", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
async def history_rig(factories, client_for, rig):
    """The owner pins a task, a CTO pins a bug, the owner unpins the task."""
    cto = await factories.user(role="cto", name="Casey CTO")
    cto_c = await client_for(cto)
    task = await _task(factories, rig, title="Refactor the importer")
    bug = await factories.issue(project_id=rig["project"].id, release_id=rig["stream_id"])
    await factories.admin_client.post(
        f"/issues/{bug.id}/triage",
        json={"outcome": "accept", "priority": "low", "assignee_id": rig["dev"].id},
    )
    await _pin(rig["dev_client"], task.id)
    await _pin(cto_c, bug.id, owner=rig["dev"].id)
    await _unpin(rig["dev_client"], task.id)
    return {**rig, "cto": cto, "task": task, "bug": bug}


@pytest.mark.asyncio
async def test_history_filters_by_actor_action_type_and_search(history_rig):
    dev_c, cto = history_rig["dev_client"], history_rig["cto"]
    task, bug = history_rig["task"], history_rig["bug"]

    everything = await _history(dev_c)
    assert everything["total"] == 3
    assert [h["issue_type"] for h in everything["items"]] == ["task", "bug", "task"]

    by_cto = await _history(dev_c, actor_id=cto.id)
    assert [(h["action"], h["issue_id"]) for h in by_cto["items"]] == [("pin", bug.id)]
    assert (await _history(dev_c, not_owner="true"))["total"] == 1

    assert [h["issue_id"] for h in (await _history(dev_c, action="unpin"))["items"]] == [task.id]
    assert {h["issue_id"] for h in (await _history(dev_c, type="bug"))["items"]} == {bug.id}

    assert (await _history(dev_c, q="importer"))["total"] == 2
    assert (await _history(dev_c, q=bug.key))["total"] == 1
    assert (await _history(dev_c, q=f"#{bug.issue_number}"))["total"] == 1


@pytest.mark.asyncio
async def test_history_facets_count_before_the_other_filters(history_rig):
    dev_c, dev, cto = history_rig["dev_client"], history_rig["dev"], history_rig["cto"]
    facets = (await _history(dev_c, action="pin"))["facets"]
    assert facets["total"] == 3
    assert facets["not_owner"] == 1
    assert facets["actions"] == {"reorder": 0, "pin": 2, "unpin": 1}
    assert facets["types"] == {"bug": 1, "task": 2}
    assert {a["actor"]["id"]: a["count"] for a in facets["actors"]} == {dev.id: 2, cto.id: 1}


@pytest.mark.asyncio
async def test_history_date_range(history_rig):
    dev_c = history_rig["dev_client"]
    async with get_engine().begin() as conn:
        await conn.execute(text(
            "UPDATE queue_history SET created_at = now() - interval '10 days' "
            "WHERE id = (SELECT min(id) FROM queue_history)"
        ))
    since = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    recent = await _history(dev_c, **{"from": since})
    assert recent["total"] == 2
    assert recent["facets"]["total"] == 2
    old = await _history(dev_c, to=since)
    assert old["total"] == 1
