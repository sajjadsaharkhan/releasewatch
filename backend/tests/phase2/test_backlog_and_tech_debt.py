"""Slice 08 (docs/phase-2/08-backlog-and-tech-debt.md): backlog and technical debt.

Backlog membership is derived (BR-04): open, board-status items with no
release. Entering it needs a category unless the item is technical debt
(BR-06). Technical debt is a task-only flag (BR-36), hidden from the backlog
by default (FR-24) and listed on its own page (FR-27).
"""

import pytest

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _task(factories, project_id, **overrides):
    return await factories.issue(project_id=project_id, type="task", **overrides)


async def _backlog(client, project_id, **params):
    resp = await client.get(f"/projects/{project_id}/backlog", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _backlog_ids(client, project_id, **params):
    return [i["id"] for i in (await _backlog(client, project_id, **params))["items"]]


async def _accept(client, issue_id, **fields):
    return await client.post(
        f"/issues/{issue_id}/triage",
        json={"outcome": "accept", "priority": "medium", **fields},
    )


async def _order(client, project_id, issue_id, **anchors):
    return await client.put(
        f"/projects/{project_id}/backlog/order", json={"issue_id": issue_id, **anchors},
    )


@pytest.fixture
async def rig(factories):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    return {"project": project, "release": release}


# ── Membership (BR-04) ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_created_without_release_is_backlog_member(factories, rig):
    features = await factories.backlog_category(project_id=rig["project"].id, name="Features")
    task = await _task(factories, rig["project"].id, backlog_category_id=features.id)
    body = await _backlog(factories.admin_client, rig["project"].id)
    assert [i["id"] for i in body["items"]] == [task.id]
    assert body["items"][0]["backlog_category"]["name"] == "Features"
    assert body["items"][0]["backlog_rank"] is not None


@pytest.mark.asyncio
async def test_task_created_in_release_is_not_a_member(factories, rig):
    await _task(factories, rig["project"].id, release_id=rig["release"].id)
    assert await _backlog_ids(factories.admin_client, rig["project"].id) == []


@pytest.mark.asyncio
async def test_moved_to_release_leaves_and_returns_with_rank_and_category(factories, rig):
    admin = factories.admin_client
    pid = rig["project"].id
    later = await factories.backlog_category(project_id=pid, name="Later")
    first = await _task(factories, pid, backlog_category_id=later.id)
    second = await _task(factories, pid)
    before = await _backlog(admin, pid)
    rank = next(i["backlog_rank"] for i in before["items"] if i["id"] == first.id)

    resp = await admin.patch(f"/issues/{first.id}", json={"release_id": rig["release"].id})
    assert resp.status_code == 200, resp.text
    assert await _backlog_ids(admin, pid) == [second.id]

    resp = await admin.patch(f"/issues/{first.id}", json={"release_id": None})
    assert resp.status_code == 200, resp.text
    after = await _backlog(admin, pid)
    assert [i["id"] for i in after["items"]] == [first.id, second.id]
    returned = after["items"][0]
    assert returned["backlog_rank"] == rank
    assert returned["backlog_category_id"] == later.id


@pytest.mark.asyncio
async def test_done_and_cancelled_items_are_never_members(factories, rig):
    admin = factories.admin_client
    pid = rig["project"].id
    done = await _task(factories, pid)
    cancelled = await _task(factories, pid)
    kept = await _task(factories, pid)
    for item, to in ((done, "done"), (cancelled, "cancelled")):
        resp = await admin.post(f"/issues/{item.id}/transition", json={"to": to})
        assert resp.status_code == 200
    assert await _backlog_ids(admin, pid) == [kept.id]


@pytest.mark.asyncio
async def test_untriaged_bug_is_not_a_member(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id)
    assert bug.status == "new"
    assert await _backlog_ids(factories.admin_client, rig["project"].id) == []


@pytest.mark.asyncio
async def test_in_progress_and_blocked_items_stay_members(factories, rig):
    admin = factories.admin_client
    pid = rig["project"].id
    task = await _task(factories, pid)
    for step in ("in_progress", "blocked"):
        resp = await admin.post(f"/issues/{task.id}/transition", json={"to": step})
        assert resp.status_code == 200
        assert await _backlog_ids(admin, pid) == [task.id]


# ── Default category (2026-09-28 — replaces the BR-06 "required" rule) ───────


@pytest.mark.asyncio
async def test_item_without_a_category_lands_in_default(factories, rig):
    pid = rig["project"].id
    default = await factories.default_category(project_id=pid)
    task = await _task(factories, pid)
    bug = await factories.issue(project_id=pid)
    debt = await _task(factories, pid, is_tech_debt=True)
    for item in (task, bug, debt):
        assert item.backlog_category_id == default.id
        assert item.backlog_category["is_default"] is True


@pytest.mark.asyncio
async def test_removing_from_release_needs_no_category(factories, rig):
    admin = factories.admin_client
    task = await _task(factories, rig["project"].id, release_id=rig["release"].id)
    resp = await admin.patch(f"/issues/{task.id}", json={"release_id": None})
    assert resp.status_code == 200, resp.text
    assert await _backlog_ids(admin, rig["project"].id) == [task.id]


@pytest.mark.asyncio
async def test_unflagging_debt_needs_no_category(factories, rig):
    task = await _task(factories, rig["project"].id, is_tech_debt=True)
    resp = await factories.admin_client.patch(f"/issues/{task.id}", json={"is_tech_debt": False})
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_category_of_another_project_is_refused(factories, rig):
    other = await factories.project()
    foreign = await factories.backlog_category(project_id=other.id)
    resp = await factories.admin_client.post("/issues", json={
        "title": "Wrong category", "type": "task", "project_id": rig["project"].id,
        "backlog_category_id": foreign.id,
    })
    assert resp.status_code == 422
    assert resp.json()["code"] == "category_not_in_project"

    task = await _task(factories, rig["project"].id)
    resp = await factories.admin_client.patch(
        f"/issues/{task.id}", json={"backlog_category_id": foreign.id},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "category_not_in_project"


@pytest.mark.asyncio
async def test_accept_keeps_default_or_takes_a_chosen_category(factories, rig):
    admin = factories.admin_client
    pid = rig["project"].id
    default = await factories.default_category(project_id=pid)
    ideas = await factories.backlog_category(project_id=pid, name="Ideas")

    plain = await factories.issue(project_id=pid)
    resp = await _accept(admin, plain.id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["backlog_category_id"] == default.id

    chosen = await factories.issue(project_id=pid)
    resp = await _accept(admin, chosen.id, backlog_category_id=ideas.id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["backlog_category_id"] == ideas.id
    assert await _backlog_ids(admin, pid) == [plain.id, chosen.id]


@pytest.mark.asyncio
async def test_accept_into_release_keeps_it_out_of_the_backlog(factories, rig):
    admin = factories.admin_client
    bug = await factories.issue(project_id=rig["project"].id)
    resp = await _accept(admin, bug.id, release_id=rig["release"].id)
    assert resp.status_code == 200, resp.text
    assert await _backlog_ids(admin, rig["project"].id) == []


# ── Technical debt (FR-24, FR-26–29, BR-36/37) ─────────────────────────────────


@pytest.mark.asyncio
async def test_ac_28_tech_debt_hidden_from_backlog_by_default(factories, rig):
    admin = factories.admin_client
    pid = rig["project"].id
    work = await _task(factories, pid)
    debt = await _task(factories, pid, is_tech_debt=True)

    hidden = await _backlog(admin, pid)
    assert [i["id"] for i in hidden["items"]] == [work.id]
    assert hidden["hidden_tech_debt_count"] == 1

    shown = await _backlog(admin, pid, include_tech_debt="true")
    assert [i["id"] for i in shown["items"]] == [work.id, debt.id]
    assert shown["hidden_tech_debt_count"] == 0


@pytest.mark.asyncio
async def test_ac_29_tech_debt_page_multi_project_filter(factories):
    admin = factories.admin_client
    projects = [await factories.project() for _ in range(3)]
    debts = [await _task(factories, p.id, is_tech_debt=True) for p in projects]
    await _task(factories, projects[0].id)  # not debt — never listed

    resp = await admin.get("/tech-debt")
    assert resp.status_code == 200, resp.text
    assert {i["id"] for i in resp.json()["items"]} == {d.id for d in debts}

    both = f"{projects[0].id},{projects[1].id}"
    resp = await admin.get("/tech-debt", params={"project_id": both})
    assert resp.status_code == 200, resp.text
    assert {i["id"] for i in resp.json()["items"]} == {debts[0].id, debts[1].id}
    assert resp.json()["total"] == 2


@pytest.mark.asyncio
async def test_tech_debt_page_filters_status_and_assignee(factories, rig):
    admin = factories.admin_client
    dev = await factories.user(role="developer")
    pid = rig["project"].id
    open_debt = await _task(factories, pid, is_tech_debt=True, assignee_id=dev.id)
    done_debt = await _task(factories, pid, is_tech_debt=True)
    await admin.post(f"/issues/{done_debt.id}/transition", json={"to": "done"})

    resp = await admin.get("/tech-debt", params={"status": "todo,in_progress,in_review,blocked"})
    assert [i["id"] for i in resp.json()["items"]] == [open_debt.id]
    resp = await admin.get("/tech-debt", params={"assignee_id": dev.id})
    assert [i["id"] for i in resp.json()["items"]] == [open_debt.id]


@pytest.mark.asyncio
async def test_ac_30_assigned_tech_debt_in_queue_with_marker(factories, client_for, rig):
    admin = factories.admin_client
    dev = await factories.user(role="developer")
    debt = await _task(factories, rig["project"].id, is_tech_debt=True)
    resp = await admin.patch(
        f"/issues/{debt.id}", json={"assignee_id": dev.id, "release_id": rig["release"].id},
    )
    assert resp.status_code == 200, resp.text

    dev_client = await client_for(dev)
    resp = await dev_client.get("/issues", params={"assignee_id": dev.id})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert [i["id"] for i in items] == [debt.id]
    assert items[0]["is_tech_debt"] is True
    assert items[0]["release_id"] == rig["release"].id


@pytest.mark.asyncio
async def test_ac_31_tech_debt_flag_rejected_on_bug(factories, rig):
    admin = factories.admin_client
    resp = await admin.post("/issues", json={
        "title": "Debt bug", "project_id": rig["project"].id, "is_tech_debt": True,
    })
    assert resp.status_code == 409
    assert resp.json()["code"] == "tech_debt_task_only"

    bug = await factories.issue(project_id=rig["project"].id)
    resp = await admin.patch(f"/issues/{bug.id}", json={"is_tech_debt": True})
    assert resp.status_code == 409
    assert resp.json()["code"] == "tech_debt_task_only"
    assert "flag_tech_debt" not in (await admin.get(f"/issues/{bug.id}")).json()["allowed_actions"]


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["qa", "developer", "product_manager", "cto"])
async def test_every_tech_role_can_flag_tech_debt_later(factories, client_for, rig, role):
    user = await factories.user(role=role)
    task = await _task(factories, rig["project"].id)
    client = await client_for(user)
    assert "flag_tech_debt" in (await client.get(f"/issues/{task.id}")).json()["allowed_actions"]
    resp = await client.patch(f"/issues/{task.id}", json={"is_tech_debt": True})
    assert resp.status_code == 200, resp.text
    assert resp.json()["is_tech_debt"] is True


@pytest.mark.asyncio
async def test_support_cannot_open_backlog_or_tech_debt(factories, client_for, rig):
    support = await client_for(await factories.user(role="support"))
    assert (await support.get(f"/projects/{rig['project'].id}/backlog")).status_code == 403
    assert (await support.get("/tech-debt")).status_code == 403


# ── Grouping and hygiene (FR-25) ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_grouped_by_category_follows_project_order(factories, rig):
    pid = rig["project"].id
    default = await factories.default_category(project_id=pid)
    first = await factories.backlog_category(project_id=pid, name="First")
    second = await factories.backlog_category(project_id=pid, name="Second")
    empty = await factories.backlog_category(project_id=pid, name="Empty")
    a = await _task(factories, pid, backlog_category_id=second.id)
    b = await _task(factories, pid, backlog_category_id=first.id)
    c = await _task(factories, pid, backlog_category_id=second.id)
    d = await _task(factories, pid)
    debt = await _task(factories, pid, is_tech_debt=True)

    body = await _backlog(
        factories.admin_client, pid, group_by="category", include_tech_debt="true",
    )
    assert [g["key"] for g in body["groups"]] == [
        str(default.id), str(first.id), str(second.id), str(empty.id), "tech_debt",
    ]
    groups = {g["key"]: g for g in body["groups"]}
    assert groups[str(default.id)]["item_ids"] == [d.id]
    assert groups[str(first.id)]["item_ids"] == [b.id]
    assert groups[str(second.id)]["item_ids"] == [a.id, c.id]
    assert groups[str(empty.id)]["count"] == 0
    assert groups[str(second.id)]["category"]["name"] == "Second"
    assert groups["tech_debt"]["item_ids"] == [debt.id]
    assert groups["tech_debt"]["category"] is None


@pytest.mark.asyncio
async def test_every_debt_task_is_grouped_as_technical_debt(factories, rig):
    """A debt task with a category still belongs in the Technical debt group —
    debt is its own pile (FR-24), the category is only its badge."""
    pid = rig["project"].id
    features = await factories.backlog_category(project_id=pid, name="Features")
    work = await _task(factories, pid, backlog_category_id=features.id)
    categorized_debt = await _task(
        factories, pid, is_tech_debt=True, backlog_category_id=features.id,
    )
    bare_debt = await _task(factories, pid, is_tech_debt=True)

    body = await _backlog(
        factories.admin_client, pid, group_by="category", include_tech_debt="true",
    )
    groups = {g["key"]: g["item_ids"] for g in body["groups"]}
    assert groups[str(features.id)] == [work.id]
    assert groups["tech_debt"] == [categorized_debt.id, bare_debt.id]

    tech_debt_page = (await factories.admin_client.get(
        "/tech-debt", params={"project_id": str(pid)},
    )).json()
    assert sorted(i["id"] for i in tech_debt_page["items"]) == sorted(groups["tech_debt"])


@pytest.mark.asyncio
async def test_hygiene_hint_counts_items_untouched_for_six_months(factories, clock, rig):
    pid = rig["project"].id
    a = await _task(factories, pid)
    b = await _task(factories, pid)
    assert (await _backlog(factories.admin_client, pid))["stale_count"] == 0
    clock.advance(days=200)
    body = await _backlog(factories.admin_client, pid)
    assert body["stale_count"] == 2
    assert body["stale_item_ids"] == [a.id, b.id]


# ── Ranking (FR-25) ───────────────────────────────────────────────────────────


@pytest.fixture
async def ranked(factories, rig):
    pid = rig["project"].id
    items = [await _task(factories, pid) for _ in range(3)]
    return pid, [i.id for i in items]


@pytest.mark.asyncio
async def test_new_members_go_to_the_bottom(factories, ranked):
    pid, ids = ranked
    assert await _backlog_ids(factories.admin_client, pid) == ids


@pytest.mark.asyncio
async def test_insert_between_two_items(factories, ranked):
    pid, (a, b, c) = ranked
    resp = await _order(factories.admin_client, pid, c, after_id=a, before_id=b)
    assert resp.status_code == 200, resp.text
    assert await _backlog_ids(factories.admin_client, pid) == [a, c, b]


@pytest.mark.asyncio
async def test_move_to_top(factories, ranked):
    pid, (a, b, c) = ranked
    assert (await _order(factories.admin_client, pid, c, before_id=a)).status_code == 200
    assert await _backlog_ids(factories.admin_client, pid) == [c, a, b]


@pytest.mark.asyncio
async def test_move_to_bottom(factories, ranked):
    pid, (a, b, c) = ranked
    assert (await _order(factories.admin_client, pid, a, after_id=c)).status_code == 200
    assert await _backlog_ids(factories.admin_client, pid) == [b, c, a]


@pytest.mark.asyncio
async def test_after_only_places_directly_below_the_anchor(factories, ranked):
    pid, (a, b, c) = ranked
    assert (await _order(factories.admin_client, pid, c, after_id=a)).status_code == 200
    assert await _backlog_ids(factories.admin_client, pid) == [a, c, b]


@pytest.mark.asyncio
async def test_renumbers_when_the_gap_collapses(factories, rig):
    admin = factories.admin_client
    pid = rig["project"].id
    top = await _task(factories, pid)
    bottom = await _task(factories, pid)
    inserted = []
    # Always insert directly under `top`: the gap above the previous insert
    # halves every time and falls below 1e-6 well before 60 inserts.
    for _ in range(60):
        item = await _task(factories, pid)
        resp = await _order(admin, pid, item.id, after_id=top.id)
        assert resp.status_code == 200, resp.text
        inserted.append(item.id)

    body = await _backlog(admin, pid)
    assert [i["id"] for i in body["items"]] == [top.id, *reversed(inserted), bottom.id]
    ranks = [i["backlog_rank"] for i in body["items"]]
    assert all(later - earlier >= 1e-6 for earlier, later in zip(ranks, ranks[1:], strict=False))


@pytest.mark.asyncio
async def test_reordering_does_not_count_as_touching_an_item(factories, clock, ranked):
    pid, (a, b, c) = ranked
    clock.advance(days=200)
    assert (await _order(factories.admin_client, pid, c, before_id=a)).status_code == 200
    assert (await _backlog(factories.admin_client, pid))["stale_count"] == 3


@pytest.mark.asyncio
async def test_order_refuses_an_item_outside_the_backlog(factories, rig, ranked):
    pid, (a, _, _) = ranked
    in_release = await _task(factories, pid, release_id=rig["release"].id)
    resp = await _order(factories.admin_client, pid, in_release.id, after_id=a)
    assert resp.status_code == 409
    assert resp.json()["code"] == "not_in_backlog"


@pytest.mark.asyncio
@pytest.mark.parametrize("role,allowed", [
    ("qa", False), ("developer", False), ("product_manager", True), ("cto", True),
])
async def test_manage_backlog_policy_on_reorder(factories, client_for, ranked, role, allowed):
    pid, (a, _, c) = ranked
    client = await client_for(await factories.user(role=role))
    body = await _backlog(client, pid)
    assert ("manage_backlog" in body["allowed_actions"]) is allowed
    resp = await _order(client, pid, c, before_id=a)
    assert resp.status_code == (200 if allowed else 403), resp.text


@pytest.mark.asyncio
async def test_developer_triage_lead_can_manage_backlog(factories, client_for):
    dev = await factories.user(role="developer")
    project = await factories.project(triage_lead_id=dev.id)
    a = await _task(factories, project.id)
    b = await _task(factories, project.id)
    client = await client_for(dev)
    assert (await _order(client, project.id, b.id, before_id=a.id)).status_code == 200


# ── Bulk move (FR-25) ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_move_moves_every_item_to_the_release(factories, rig, ranked):
    admin = factories.admin_client
    pid, (a, b, c) = ranked
    resp = await admin.post(
        "/issues/bulk-move", json={"issue_ids": [a, c], "release_id": rig["release"].id},
    )
    assert resp.status_code == 200, resp.text
    assert sorted(resp.json()["moved_ids"]) == sorted([a, c])
    assert all(i["release_id"] == rig["release"].id for i in resp.json()["items"])
    assert await _backlog_ids(admin, pid) == [b]


@pytest.mark.asyncio
async def test_bulk_move_is_all_or_nothing(factories, rig, ranked):
    admin = factories.admin_client
    pid, ids = ranked
    a, b, _ = ids
    other_project = await factories.project()
    stranger = await _task(factories, other_project.id)

    resp = await admin.post(
        "/issues/bulk-move",
        json={"issue_ids": [a, stranger.id, b], "release_id": rig["release"].id},
    )
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "bulk_move_failed"
    assert list(body["errors"]) == [str(stranger.id)]
    assert await _backlog_ids(admin, pid) == ids
    assert await _backlog_ids(admin, other_project.id) == [stranger.id]


@pytest.mark.asyncio
async def test_bulk_move_needs_manage_backlog(factories, client_for, rig, ranked):
    _, (a, _, _) = ranked
    qa = await client_for(await factories.user(role="qa"))
    resp = await qa.post(
        "/issues/bulk-move", json={"issue_ids": [a], "release_id": rig["release"].id},
    )
    assert resp.status_code == 403


# ── Project change (BR-05) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_project_change_blocked_while_item_has_a_release(factories, rig):
    admin = factories.admin_client
    other = await factories.project()
    task = await _task(factories, rig["project"].id, release_id=rig["release"].id)
    resp = await admin.patch(f"/issues/{task.id}", json={"project_id": other.id})
    assert resp.status_code == 409
    assert resp.json()["code"] == "move_has_release"


@pytest.mark.asyncio
async def test_project_change_moves_a_backlog_item_to_the_new_backlog(factories, rig):
    admin = factories.admin_client
    other = await factories.project()
    existing = await _task(factories, other.id)
    task = await _task(factories, rig["project"].id)
    resp = await admin.patch(f"/issues/{task.id}", json={"project_id": other.id})
    assert resp.status_code == 200, resp.text
    assert await _backlog_ids(admin, other.id) == [existing.id, task.id]
    assert await _backlog_ids(admin, rig["project"].id) == []


@pytest.mark.asyncio
async def test_release_from_another_project_is_refused(factories, rig):
    other = await factories.project()
    other_release = await factories.release(project_id=other.id)
    task = await _task(factories, rig["project"].id)
    resp = await factories.admin_client.patch(
        f"/issues/{task.id}", json={"release_id": other_release.id},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "release_project_mismatch"


# ── Bulk category change (2026-09-24, user request) ────────────────────────────


async def _set_category(client, project_id, issue_ids, category_id):
    return await client.post(
        f"/projects/{project_id}/backlog/category",
        json={"issue_ids": issue_ids, "backlog_category_id": category_id},
    )


@pytest.mark.asyncio
async def test_bulk_category_moves_items_to_another_group(factories, ranked):
    admin = factories.admin_client
    pid, (a, b, c) = ranked
    default = await factories.default_category(project_id=pid)
    later = await factories.backlog_category(project_id=pid, name="Later")
    resp = await _set_category(admin, pid, [a, c], later.id)
    assert resp.status_code == 200, resp.text
    assert sorted(resp.json()["updated_ids"]) == sorted([a, c])

    body = await _backlog(admin, pid, group_by="category")
    groups = {g["key"]: g["item_ids"] for g in body["groups"]}
    assert groups[str(later.id)] == [a, c]
    assert groups[str(default.id)] == [b]
    # Rank order is untouched — only the grouping changes.
    assert [i["id"] for i in body["items"]] == [a, b, c]

    events = (await admin.get(f"/issues/{a}/timeline", params={"size": 50})).json()["items"]
    changes = [e for e in events if e["event_type"] == "backlog_category_changed"]
    assert changes[-1]["meta"]["from"]["name"] == "Default"
    assert changes[-1]["meta"]["to"] == {
        "id": later.id, "name": "Later", "icon": later.icon, "color": later.color,
        "is_default": False,
    }


@pytest.mark.asyncio
async def test_bulk_category_skips_items_already_in_it(factories, ranked):
    pid, (a, b, _) = ranked
    default = await factories.default_category(project_id=pid)
    resp = await _set_category(factories.admin_client, pid, [a, b], default.id)
    assert resp.status_code == 200, resp.text
    assert resp.json()["updated_ids"] == []


@pytest.mark.asyncio
async def test_bulk_category_is_all_or_nothing(factories, ranked):
    admin = factories.admin_client
    pid, ids = ranked
    later = await factories.backlog_category(project_id=pid, name="Later")
    other = await _task(factories, (await factories.project()).id)
    resp = await _set_category(admin, pid, [ids[0], other.id], later.id)
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "bulk_category_failed"
    assert list(body["errors"]) == [str(other.id)]
    body = await _backlog(admin, pid, group_by="category")
    groups = {g["key"]: g["item_ids"] for g in body["groups"]}
    assert groups[str(later.id)] == []


@pytest.mark.asyncio
async def test_bulk_category_needs_manage_backlog(factories, client_for, ranked):
    pid, (a, _, _) = ranked
    later = await factories.backlog_category(project_id=pid, name="Later")
    qa = await client_for(await factories.user(role="qa"))
    assert (await _set_category(qa, pid, [a], later.id)).status_code == 403


@pytest.mark.asyncio
async def test_bulk_category_refuses_another_projects_category(factories, ranked):
    pid, (a, _, _) = ranked
    foreign = await factories.backlog_category(project_id=(await factories.project()).id)
    resp = await _set_category(factories.admin_client, pid, [a], foreign.id)
    assert resp.status_code == 422
    assert resp.json()["code"] == "category_not_in_project"
