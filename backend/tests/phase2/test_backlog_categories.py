"""Backlog categories per project (2026-09-28 follow-up to slice 08).

Every project has a fixed Default (created with it, always first, never
edited, moved or deleted). CTO and Admin manage the rest in Settings. Deleting
a category moves its items to Default with a timeline entry and no
notification. Moving an item to another project lands it in that project's
Default.
"""

import pytest


def _path(project_id, suffix=""):
    return f"/projects/{project_id}/backlog-categories{suffix}"


async def _list(client, project_id):
    resp = await client.get(_path(project_id))
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
async def project(factories):
    return await factories.project()


# ── Default ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_every_new_project_starts_with_only_default(factories, project):
    body = await _list(factories.admin_client, project.id)
    assert [c["name"] for c in body["categories"]] == ["Default"]
    default = body["categories"][0]
    assert default["is_default"] is True
    assert default["icon"] == "inbox" and default["color"] == "zinc"
    assert project.backlog_category_count == 1


@pytest.mark.asyncio
async def test_default_is_fixed(factories, project):
    admin = factories.admin_client
    default = await factories.default_category(project_id=project.id)
    resp = await admin.patch(_path(project.id, f"/{default.id}"), json={"name": "General"})
    assert resp.status_code == 409 and resp.json()["code"] == "default_category_locked"
    resp = await admin.delete(_path(project.id, f"/{default.id}"))
    assert resp.status_code == 409 and resp.json()["code"] == "default_category_locked"
    extra = await factories.backlog_category(project_id=project.id)
    resp = await admin.put(_path(project.id, "/order"), json={"ids": [extra.id, default.id]})
    assert resp.status_code == 409 and resp.json()["code"] == "default_category_locked"


# ── Create / update / reorder ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_update_and_reorder(factories, project):
    admin = factories.admin_client
    a = await factories.backlog_category(project_id=project.id, name="Features")
    b = await factories.backlog_category(
        project_id=project.id, name="Ideas", icon="lightbulb", color="violet"
    )
    assert (a.position, b.position) == (1, 2)

    resp = await admin.patch(
        _path(project.id, f"/{a.id}"),
        json={"name": "Feature requests", "icon": "rocket", "color": "sky"},
    )
    assert resp.status_code == 200, resp.text
    assert (resp.json()["name"], resp.json()["icon"], resp.json()["color"]) == (
        "Feature requests",
        "rocket",
        "sky",
    )

    resp = await admin.put(_path(project.id, "/order"), json={"ids": [b.id, a.id]})
    assert resp.status_code == 200, resp.text
    assert [c["name"] for c in resp.json()["categories"]] == [
        "Default",
        "Ideas",
        "Feature requests",
    ]


@pytest.mark.asyncio
async def test_reorder_needs_every_non_default_category_once(factories, project):
    a = await factories.backlog_category(project_id=project.id)
    await factories.backlog_category(project_id=project.id)
    resp = await factories.admin_client.put(_path(project.id, "/order"), json={"ids": [a.id]})
    assert resp.status_code == 422 and resp.json()["code"] == "category_order_mismatch"


@pytest.mark.asyncio
async def test_names_are_unique_per_project_ignoring_case(factories, project):
    admin = factories.admin_client
    await factories.backlog_category(project_id=project.id, name="Ideas")
    for name in ("ideas", "  IDEAS  ", "default"):
        resp = await admin.post(
            _path(project.id), json={"name": name, "icon": "star", "color": "pink"}
        )
        assert resp.status_code == 409, name
        assert resp.json()["code"] == "category_name_taken"
    # Another project may use the same name.
    other = await factories.project()
    assert (await factories.backlog_category(project_id=other.id, name="Ideas")).name == "Ideas"


@pytest.mark.asyncio
async def test_name_icon_and_colour_are_validated(factories, project):
    admin = factories.admin_client
    for body in (
        {"name": "", "icon": "star", "color": "pink"},
        {"name": "x" * 41, "icon": "star", "color": "pink"},
        {"name": "Ok", "icon": "not-an-icon", "color": "pink"},
        {"name": "Ok", "icon": "star", "color": "#ff0000"},
        {"name": "Ok", "icon": "star", "color": "red"},  # red is priority's, not curated
    ):
        resp = await admin.post(_path(project.id), json=body)
        assert resp.status_code == 422, body


@pytest.mark.asyncio
async def test_a_project_holds_at_most_twenty_categories(factories, project):
    for _ in range(19):
        await factories.backlog_category(project_id=project.id)
    resp = await factories.admin_client.post(
        _path(project.id),
        json={"name": "One too many", "icon": "star", "color": "pink"},
    )
    assert resp.status_code == 409 and resp.json()["code"] == "category_limit_reached"


# ── Who may manage ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "role,allowed",
    [
        ("cto", True),
        ("product_manager", False),
        ("developer", False),
        ("qa", False),
    ],
)
async def test_only_cto_and_admin_manage_categories(factories, client_for, project, role, allowed):
    client = await client_for(await factories.user(role=role))
    body = await _list(client, project.id)  # every tech role can read them (pickers)
    assert body["can_manage"] is allowed
    resp = await client.post(
        _path(project.id), json={"name": "Mine", "icon": "star", "color": "pink"}
    )
    assert resp.status_code == (201 if allowed else 403), resp.text


@pytest.mark.asyncio
async def test_support_cannot_read_categories(factories, client_for, project):
    support = await client_for(await factories.user(role="support"))
    assert (await support.get(_path(project.id))).status_code == 403


# ── Delete moves items to Default ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_moves_every_item_to_default_quietly(factories, client_for, project):
    admin = factories.admin_client
    dev = await factories.user(role="developer")
    default = await factories.default_category(project_id=project.id)
    doomed = await factories.backlog_category(project_id=project.id, name="Doomed")
    open_task = await factories.issue(
        project_id=project.id,
        type="task",
        backlog_category_id=doomed.id,
        assignee_id=dev.id,
    )
    done_task = await factories.issue(
        project_id=project.id,
        type="task",
        backlog_category_id=doomed.id,
    )
    await admin.post(f"/issues/{done_task.id}/transition", json={"to": "done"})
    bug = await factories.issue(project_id=project.id, backlog_category_id=doomed.id)

    listing = await _list(admin, project.id)
    assert next(c for c in listing["categories"] if c["id"] == doomed.id)["item_count"] == 3

    dev_client = await client_for(dev)
    inbox_before = (await dev_client.get("/inbox")).json()

    resp = await admin.delete(_path(project.id, f"/{doomed.id}"))
    assert resp.status_code == 200, resp.text
    assert resp.json()["moved_count"] == 3
    assert resp.json()["default_category"]["id"] == default.id

    for item in (open_task, done_task, bug):
        detail = (await admin.get(f"/issues/{item.id}")).json()
        assert detail["backlog_category_id"] == default.id
        events = (await admin.get(f"/issues/{item.id}/timeline", params={"size": 50})).json()[
            "items"
        ]
        change = [e for e in events if e["event_type"] == "backlog_category_changed"][-1]
        assert change["meta"]["from"]["name"] == "Doomed"
        assert change["meta"]["to"]["name"] == "Default"
        assert change["meta"]["reason"] == "category_deleted"

    # No notification for anyone.
    assert (await dev_client.get("/inbox")).json() == inbox_before
    assert [c["name"] for c in (await _list(admin, project.id))["categories"]] == ["Default"]


@pytest.mark.asyncio
async def test_delete_keeps_items_untouched_for_the_hygiene_hint(factories, clock, project):
    doomed = await factories.backlog_category(project_id=project.id)
    await factories.issue(project_id=project.id, type="task", backlog_category_id=doomed.id)
    clock.advance(days=200)
    await factories.admin_client.delete(_path(project.id, f"/{doomed.id}"))
    body = (await factories.admin_client.get(f"/projects/{project.id}/backlog")).json()
    assert body["stale_count"] == 1


# ── Moving projects ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_moving_to_another_project_lands_in_its_default(factories, project):
    admin = factories.admin_client
    here = await factories.backlog_category(project_id=project.id, name="Here")
    target = await factories.project()
    target_default = await factories.default_category(project_id=target.id)
    task = await factories.issue(project_id=project.id, type="task", backlog_category_id=here.id)

    resp = await admin.post(f"/issues/{task.id}/move", json={"project_id": target.id})
    assert resp.status_code == 200, resp.text
    assert resp.json()["backlog_category_id"] == target_default.id
    # The sidebar renders these, so they must describe the new project, not the old.
    assert resp.json()["project_id"] == target.id
    assert resp.json()["project_name"] == target.name
    assert resp.json()["backlog_category"]["id"] == target_default.id


@pytest.mark.asyncio
async def test_moving_projects_may_pick_a_category_of_the_target(factories, project):
    target = await factories.project()
    there = await factories.backlog_category(project_id=target.id, name="There")
    task = await factories.issue(project_id=project.id, type="task")
    resp = await factories.admin_client.post(
        f"/issues/{task.id}/move",
        json={"project_id": target.id, "backlog_category_id": there.id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["backlog_category_id"] == there.id


@pytest.mark.asyncio
async def test_changing_category_returns_the_new_category(factories, project):
    # The sidebar badge renders the nested object, so it must match the new id.
    here = await factories.backlog_category(project_id=project.id, name="Here")
    task = await factories.issue(project_id=project.id, type="task")
    resp = await factories.admin_client.patch(
        f"/issues/{task.id}", json={"backlog_category_id": here.id}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["backlog_category_id"] == here.id
    assert resp.json()["backlog_category"]["name"] == "Here"


@pytest.mark.asyncio
async def test_triage_move_lands_in_the_target_default(factories, project):
    target = await factories.project()
    target_default = await factories.default_category(project_id=target.id)
    bug = await factories.issue(project_id=project.id)
    resp = await factories.admin_client.post(
        f"/issues/{bug.id}/move", json={"project_id": target.id}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["backlog_category_id"] == target_default.id
