"""Slice 22 — the To review tab in My Work.

docs/phase-2/22-review-tab.md, PRD v3.1 FR-72/FR-73, BR-73, AC-99/AC-100.
Observed through ``GET /review-queue``. Timeline rows are stamped with direct
SQL where a test needs a known wait (the timeline clock is not injectable).
"""

from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy import text

from app.db.session import get_engine


@pytest_asyncio.fixture
async def rig(factories, client_for):
    qa = await factories.user(role="qa")
    dev = await factories.user(role="developer")
    support = await factories.user(role="support")
    cto = await factories.user(role="cto")
    projects = {}
    for name in ("Alpha", "Bravo", "Charlie"):
        project = await factories.project(name=name)
        projects[name] = {
            "project": project,
            "stream_id": await factories.stream_id(project_id=project.id),
        }
    return {
        "admin": factories.admin_client, "projects": projects,
        "qa": qa, "qa_client": await client_for(qa),
        "dev": dev, "dev_client": await client_for(dev),
        "support": support, "support_client": await client_for(support),
        "cto_client": await client_for(cto),
    }


async def _item(factories, rig, project="Alpha", *, to="to_review", type="task",
                priority="medium", assignee=None, **fields):
    p = rig["projects"][project]
    issue = await factories.issue(
        project_id=p["project"].id, release_id=p["stream_id"], type=type, priority=priority,
        assignee_id=None if assignee == "nobody" else (assignee or rig["dev"]).id, **fields,
    )
    if to == "to_review":
        steps = ["to_review"]
    elif to == "in_review":
        steps = ["in_progress", "in_review"]
    else:
        steps = [to] if to != "todo" else []
    for step in steps:
        resp = await rig["admin"].post(f"/issues/{issue.id}/transition", json={"to": step})
        assert resp.status_code == 200, resp.text
    return issue


async def _queue(client, **params):
    resp = await client.get("/review-queue", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ids(body):
    return [r["id"] for r in body["items"]]


async def _stamp(issue_id, ago: timedelta):
    """Move the item's latest status_changed event ``ago`` into the past."""
    async with get_engine().begin() as conn:
        await conn.execute(
            text(
                "UPDATE issue_timeline SET created_at = :t WHERE id = ("
                " SELECT id FROM issue_timeline WHERE issue_id = :i"
                " AND event_type = 'status_changed' ORDER BY id DESC LIMIT 1)"
            ),
            {"t": datetime.now(UTC) - ago, "i": issue_id},
        )


# ── AC-99 ─────────────────────────────────────────────────────────────────────


async def test_ac_99_lists_review_items_from_every_project_grouped_and_ordered(factories, rig):
    # Alpha: a high To review, a critical To review, a medium In review
    a_high = await _item(factories, rig, "Alpha", priority="high")
    a_crit = await _item(factories, rig, "Alpha", priority="critical")
    a_inrev = await _item(factories, rig, "Alpha", to="in_review", priority="medium")
    b_none = await _item(factories, rig, "Bravo", type="bug", priority=None, assignee="nobody")
    b_low = await _item(factories, rig, "Bravo", priority="low")
    c_inrev = await _item(factories, rig, "Charlie", to="in_review", priority="critical")
    # Never listed
    await _item(factories, rig, "Alpha", to="todo")
    await _item(factories, rig, "Alpha", to="in_progress")
    verified = await _item(factories, rig, "Alpha", to="in_review")
    await rig["qa_client"].post(f"/issues/{verified.id}/verify", json={"outcome": "pass"})

    body = await _queue(rig["qa_client"])

    assert _ids(body) == [
        a_crit.id, a_high.id, a_inrev.id,   # Alpha: To review (critical, high), In review
        b_low.id, b_none.id,                 # Bravo: low before unrated
        c_inrev.id,
    ]
    assert body["counts"] == {"to_review": 4, "in_review": 2, "total": 6}
    assert body["truncated"] is False
    row = body["items"][0]
    assert row["key"].startswith("TASK-") and row["project"]["name"] == "Alpha"
    assert row["assignee"]["id"] == rig["dev"].id
    assert row["container"]["kind"] == "stream" and row["status"] == "to_review"
    assert row["waiting_since"] and "cycle_number" in row


async def test_ac_99_longest_wait_first_within_the_same_priority(factories, rig):
    newer = await _item(factories, rig, priority="high")
    older = await _item(factories, rig, priority="high")
    await _stamp(older.id, timedelta(days=3))
    await _stamp(newer.id, timedelta(hours=1))
    assert _ids(await _queue(rig["qa_client"])) == [older.id, newer.id]


async def test_ac_99_the_default_tab_is_the_clients_job_but_both_roles_get_the_list(factories, rig):
    item = await _item(factories, rig)
    assert _ids(await _queue(rig["dev_client"])) == [item.id]
    assert _ids(await _queue(rig["cto_client"])) == [item.id]


async def test_an_item_assigned_to_the_qa_user_is_listed_too(factories, rig):
    mine = await _item(factories, rig, assignee=rig["qa"])
    assert _ids(await _queue(rig["qa_client"])) == [mine.id]


async def test_support_is_refused(rig):
    resp = await rig["support_client"].get("/review-queue")
    assert resp.status_code == 403


async def test_deleted_items_and_archived_projects_are_left_out(factories, rig):
    gone = await _item(factories, rig, "Alpha")
    kept = await _item(factories, rig, "Bravo")
    archived = await _item(factories, rig, "Charlie")
    assert (await rig["admin"].delete(f"/issues/{gone.id}")).status_code in (200, 204)
    slug = rig["projects"]["Charlie"]["project"].slug
    assert (await rig["admin"].delete(f"/projects/{slug}")).status_code in (200, 204)
    body = await _queue(rig["qa_client"])
    assert _ids(body) == [kept.id]
    assert archived.id not in _ids(body)
    assert body["counts"]["total"] == 1


# ── Filters and counts ────────────────────────────────────────────────────────


async def test_filters_by_project_type_and_status_and_counts_follow_the_project_only(factories, rig):
    a_task = await _item(factories, rig, "Alpha", type="task")
    a_bug = await _item(factories, rig, "Alpha", type="bug", to="in_review")
    b_task = await _item(factories, rig, "Bravo", type="task")
    qa = rig["qa_client"]
    alpha = rig["projects"]["Alpha"]["project"].id
    bravo = rig["projects"]["Bravo"]["project"].id

    by_project = await _queue(qa, project_ids=[alpha])
    assert set(_ids(by_project)) == {a_task.id, a_bug.id}
    assert by_project["counts"] == {"to_review": 1, "in_review": 1, "total": 2}

    both = await _queue(qa, project_ids=[alpha, bravo])
    assert set(_ids(both)) == {a_task.id, a_bug.id, b_task.id}

    by_type = await _queue(qa, type="bug")
    assert _ids(by_type) == [a_bug.id]
    assert by_type["counts"]["total"] == 3  # type does not move the counter

    by_status = await _queue(qa, status="in_review")
    assert _ids(by_status) == [a_bug.id]
    assert by_status["counts"] == {"to_review": 2, "in_review": 1, "total": 3}

    refused = await qa.get("/review-queue", params={"status": "verified"})
    assert refused.status_code == 422


# ── waiting_since ─────────────────────────────────────────────────────────────


async def test_waiting_since_resets_on_a_move_into_the_next_review_status(factories, rig):
    item = await _item(factories, rig)
    await _stamp(item.id, timedelta(days=5))
    before = (await _queue(rig["qa_client"]))["items"][0]["waiting_since"]
    resp = await rig["qa_client"].post(f"/issues/{item.id}/transition", json={"to": "in_review"})
    assert resp.status_code == 200, resp.text
    after = (await _queue(rig["qa_client"]))["items"][0]
    assert after["status"] == "in_review"
    assert after["waiting_since"] > before
    waited = datetime.now(UTC) - datetime.fromisoformat(after["waiting_since"])
    assert waited < timedelta(minutes=5)


async def test_waiting_since_is_the_latest_move_into_the_current_status(factories, rig):
    item = await _item(factories, rig)
    await _stamp(item.id, timedelta(days=4))
    body = (await _queue(rig["qa_client"]))["items"][0]
    waited = datetime.now(UTC) - datetime.fromisoformat(body["waiting_since"])
    assert timedelta(days=3, hours=23) < waited < timedelta(days=4, hours=1)


# ── AC-100 ────────────────────────────────────────────────────────────────────


async def test_ac_100_verify_removes_the_item_and_lowers_the_counter(factories, rig):
    item = await _item(factories, rig, to="in_review")
    other = await _item(factories, rig)
    assert (await _queue(rig["qa_client"]))["counts"]["total"] == 2
    resp = await rig["qa_client"].post(f"/issues/{item.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200, resp.text
    body = await _queue(rig["qa_client"])
    assert _ids(body) == [other.id]
    assert body["counts"] == {"to_review": 1, "in_review": 0, "total": 1}


async def test_ac_100_reject_removes_the_item_and_lowers_the_counter(factories, rig):
    item = await _item(factories, rig, to="in_review")
    resp = await rig["qa_client"].post(
        f"/issues/{item.id}/reject", json={"comment": "Still broken on the empty state."},
    )
    assert resp.status_code == 200, resp.text
    body = await _queue(rig["qa_client"])
    assert item.id not in _ids(body)
    assert body["counts"]["total"] == 0
