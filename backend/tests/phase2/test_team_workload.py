"""Slice 11 — Team overview: the Workload view.

docs/phase-2/11-team-overview.md (PRD v3 FR-43, AC-48). ``GET /team/workload``
lists every active assignable user with their In progress items, the next three
queue items, and open/pinned counts — CTO and Admin only.
"""

from contextlib import contextmanager

import pytest
from sqlalchemy import event

from app.db.session import get_engine

# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def rig(factories):
    project = await factories.project()
    return {"project": project, "stream_id": await factories.stream_id(project_id=project.id)}


async def _task(factories, rig, assignee, priority="medium", project=None, stream_id=None):
    """A To do task in the Stream, assigned to ``assignee``."""
    return await factories.issue(
        project_id=(project or rig["project"]).id, release_id=stream_id or rig["stream_id"],
        type="task", priority=priority, assignee_id=assignee.id,
    )


async def _transition(client, issue_id, to):
    resp = await client.post(f"/issues/{issue_id}/transition", json={"to": to})
    assert resp.status_code == 200, resp.text


async def _pin(client, owner_id, issue_id):
    resp = await client.post(f"/users/{owner_id}/queue/pins", json={"issue_id": issue_id})
    assert resp.status_code == 200, resp.text


async def _workload(client, **params):
    resp = await client.get("/team/workload", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _row(workload, user):
    rows = [r for r in workload if r["user"]["id"] == user.id]
    assert len(rows) == 1, f"{user.username} listed {len(rows)} times"
    return rows[0]


def _ids(cards):
    return [c["id"] for c in cards]


@contextmanager
def _count_queries():
    """Count every SQL statement the app runs inside the block."""
    counter = {"n": 0}

    def _before(*_args, **_kwargs):
        counter["n"] += 1

    engine = get_engine().sync_engine
    event.listen(engine, "before_cursor_execute", _before)
    try:
        yield counter
    finally:
        event.remove(engine, "before_cursor_execute", _before)


# ── Access (AC-48) ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["developer", "pm", "qa", "support"])
async def test_ac_48_workload_denied_to_developer(factories, client_for, role):
    user = await factories.user(role=role)
    resp = await (await client_for(user)).get("/team/workload")
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["cto", "admin"])
async def test_workload_open_to_cto_and_admin(factories, client_for, role):
    user = await factories.user(role=role)
    resp = await (await client_for(user)).get("/team/workload")
    assert resp.status_code == 200, resp.text


# ── Content (FR-43) ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workload_lists_each_active_assignable_user_once(factories, client_for):
    dev = await factories.user(role="developer")
    qa = await factories.user(role="qa")
    support = await factories.user(role="support")
    gone = await factories.user(role="developer")
    resp = await factories.admin_client.patch(f"/team/{gone.id}/deactivate")
    assert resp.status_code == 200, resp.text

    workload = await _workload(factories.admin_client)
    ids = {r["user"]["id"] for r in workload}
    assert {dev.id, qa.id} <= ids
    assert support.id not in ids
    assert gone.id not in ids
    # Nothing assigned: listed with empty work and zero counts.
    row = _row(workload, qa)
    assert row["in_progress"] == [] and row["next"] == []
    assert row["counts"] == {"open": 0, "pinned": 0}
    # People are listed by name, never ranked by load (spec: no performance scoring).
    names = [r["user"]["name"] for r in workload]
    assert names == sorted(names, key=str.casefold)


@pytest.mark.asyncio
async def test_workload_shows_in_progress_next_three_and_counts(factories, rig):
    admin = factories.admin_client
    ana = await factories.user(role="developer", name="Ana")
    ben = await factories.user(role="qa", name="Ben")
    cy = await factories.user(role="pm", name="Cy")

    # Ana: six items; default order is critical, high, medium, medium, low, low.
    a_crit = await _task(factories, rig, ana, "critical")
    a_high = await _task(factories, rig, ana, "high")
    a_med1 = await _task(factories, rig, ana, "medium")
    a_med2 = await _task(factories, rig, ana, "medium")
    a_low1 = await _task(factories, rig, ana, "low")
    a_low2 = await _task(factories, rig, ana, "low")
    await _transition(admin, a_high.id, "in_progress")
    # Pins go first, in pin order.
    await _pin(admin, ana.id, a_low2.id)
    await _pin(admin, ana.id, a_med2.id)

    # Ben: two items in progress, one waiting.
    b1 = await _task(factories, rig, ben, "high")
    b2 = await _task(factories, rig, ben, "medium")
    b3 = await _task(factories, rig, ben, "low")
    await _transition(admin, b1.id, "in_progress")
    await _transition(admin, b2.id, "in_progress")
    await _pin(admin, ben.id, b2.id)

    # Cy: one item, pinned.
    c1 = await _task(factories, rig, cy, "low")
    await _pin(admin, cy.id, c1.id)

    workload = await _workload(admin)

    row = _row(workload, ana)
    assert _ids(row["in_progress"]) == [a_high.id]
    # Queue order minus what's already in progress, first three only.
    assert _ids(row["next"]) == [a_low2.id, a_med2.id, a_crit.id]
    assert row["counts"] == {"open": 6, "pinned": 2}
    assert [c["pinned"] for c in row["next"]] == [True, True, False]
    assert a_med1.id not in _ids(row["next"]) and a_low1.id not in _ids(row["next"])

    row = _row(workload, ben)
    # In progress follows queue order too: the pinned one first.
    assert _ids(row["in_progress"]) == [b2.id, b1.id]
    assert _ids(row["next"]) == [b3.id]
    assert row["counts"] == {"open": 3, "pinned": 1}

    row = _row(workload, cy)
    assert row["in_progress"] == []
    assert _ids(row["next"]) == [c1.id]
    assert row["counts"] == {"open": 1, "pinned": 1}

    # Cards are the slim WorkItemCard, with the project.
    card = _row(workload, ana)["in_progress"][0]
    assert card["key"] == f"TASK-{a_high.issue_number}"
    assert card["project"]["id"] == rig["project"].id
    assert card["status"] == "in_progress"


@pytest.mark.asyncio
async def test_workload_counts_ignore_dormant_entries(factories, rig):
    admin = factories.admin_client
    dev = await factories.user(role="developer")
    keep = await _task(factories, rig, dev, "high")
    pinned_done = await _task(factories, rig, dev, "medium")
    done = await _task(factories, rig, dev, "low")
    await _pin(admin, dev.id, pinned_done.id)
    await _transition(admin, pinned_done.id, "done")
    await _transition(admin, done.id, "done")

    row = _row(await _workload(admin), dev)
    assert row["counts"] == {"open": 1, "pinned": 0}
    assert _ids(row["next"]) == [keep.id]

    # A reject brings the entry back — and into the counts.
    resp = await admin.post(f"/issues/{done.id}/reject", json={"comment": "Still broken"})
    assert resp.status_code == 200, resp.text
    row = _row(await _workload(admin), dev)
    assert row["counts"] == {"open": 2, "pinned": 0}


@pytest.mark.asyncio
async def test_workload_hides_deleted_items(factories, rig):
    admin = factories.admin_client
    dev = await factories.user(role="developer")
    item = await _task(factories, rig, dev)
    resp = await admin.delete(f"/issues/{item.id}")
    assert resp.status_code in (200, 204), resp.text
    row = _row(await _workload(admin), dev)
    assert row["counts"] == {"open": 0, "pinned": 0}


@pytest.mark.asyncio
async def test_workload_counts_every_open_board_status(factories, rig):
    """Rejected, To review, In review and Blocked are open work too (BR-38):
    counted, and listed in Up next in queue order — only In progress is "Now"."""
    admin = factories.admin_client
    dev = await factories.user(role="developer")
    rejected = await _task(factories, rig, dev, "critical")
    to_review = await _task(factories, rig, dev, "high")
    in_review = await _task(factories, rig, dev, "medium")
    blocked = await _task(factories, rig, dev, "low")
    for item, to in ((to_review, "to_review"), (in_review, "in_review"), (blocked, "blocked")):
        await _transition(admin, item.id, to)
    await _transition(admin, rejected.id, "in_review")
    resp = await admin.post(f"/issues/{rejected.id}/reject", json={"comment": "Still broken"})
    assert resp.status_code == 200, resp.text

    row = _row(await _workload(admin), dev)
    assert row["counts"] == {"open": 4, "pinned": 0}
    assert row["in_progress"] == []
    assert _ids(row["next"]) == [rejected.id, to_review.id, in_review.id]
    assert [c["status"] for c in row["next"]] == ["rejected", "to_review", "in_review"]


@pytest.mark.asyncio
async def test_workload_marks_locked_pins(factories, client_for, rig):
    """A CTO/Admin pin on someone else's queue is locked (BR-41); the owner's own isn't."""
    dev = await factories.user(role="developer")
    dev_client = await client_for(dev)
    locked = await _task(factories, rig, dev, "high")
    own = await _task(factories, rig, dev, "low")
    await _pin(factories.admin_client, dev.id, locked.id)
    await _pin(dev_client, "me", own.id)

    cards = {c["id"]: c for c in _row(await _workload(factories.admin_client), dev)["next"]}
    assert cards[locked.id]["pinned"] and cards[locked.id]["pin_locked"]
    assert cards[own.id]["pinned"] and not cards[own.id]["pin_locked"]


# ── Filters ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workload_filters_by_role(factories):
    dev = await factories.user(role="developer")
    qa = await factories.user(role="qa")
    workload = await _workload(factories.admin_client, role="qa")
    ids = {r["user"]["id"] for r in workload}
    assert qa.id in ids and dev.id not in ids
    assert {r["user"]["role"] for r in workload} == {"qa"}


@pytest.mark.asyncio
async def test_workload_filters_by_project_involvement(factories, rig):
    inside = await factories.user(role="developer")
    outside = await factories.user(role="developer")
    other = await factories.project()
    other_stream = await factories.stream_id(project_id=other.id)
    await _task(factories, rig, inside)
    await _task(factories, rig, outside, project=other, stream_id=other_stream)

    workload = await _workload(factories.admin_client, project_id=rig["project"].id)
    ids = {r["user"]["id"] for r in workload}
    assert inside.id in ids and outside.id not in ids


@pytest.mark.asyncio
async def test_workload_project_filter_ignores_done_work(factories, rig):
    """Only open queued work makes someone "working in" a project — a Done item
    (a dormant entry) doesn't."""
    finished = await factories.user(role="developer")
    item = await _task(factories, rig, finished)
    await _transition(factories.admin_client, item.id, "done")

    workload = await _workload(factories.admin_client, project_id=rig["project"].id)
    assert finished.id not in {r["user"]["id"] for r in workload}


# ── Query count guard ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_workload_query_count_is_fixed(factories, rig):
    """Never one query per user: the same count for 3 people as for 20."""
    admin = factories.admin_client

    async def _staff(n):
        for i in range(n):
            user = await factories.user(role="developer")
            first = await _task(factories, rig, user, "high")
            await _task(factories, rig, user, "low")
            if i % 2 == 0:
                await _transition(admin, first.id, "in_progress")
            else:
                await _pin(admin, user.id, first.id)

    await _staff(3)
    with _count_queries() as few:
        assert len(await _workload(admin)) >= 3
    await _staff(17)
    with _count_queries() as many:
        assert len(await _workload(admin)) >= 20

    assert few["n"] > 0
    assert many["n"] == few["n"], (few["n"], many["n"])
    assert many["n"] <= 12, many["n"]
