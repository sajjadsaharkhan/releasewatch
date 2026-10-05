"""Slice 04 — the PRD §7.3 permission matrix (plus the §9.2 flag rules), over HTTP.

One parametrized test per capability row × role. Each case makes the
smallest request that exercises the capability and expects success, 403
(the role can't), 404 (Support may not know the item exists — BR-30), or
422 (Support can't be assigned — BR-32).

Rows with no endpoint yet (support report, recurrence, technical debt,
queues, templates, search settings) are covered by ``test_policy.py`` until
their slices land. Team overview's endpoint is tested by role in
``test_team_workload.py`` (AC-48).
"""

from types import SimpleNamespace

import pytest

ROLES = ["support", "qa", "developer", "product_manager", "cto", "admin"]
TECH = {"qa", "developer", "product_manager", "cto", "admin"}


@pytest.fixture
async def world(factories, client_for):
    """One user per role, a project led by someone else, and a new bug in it."""
    users = {role: await factories.user(role=role) for role in ROLES}
    lead = await factories.user(role="developer")
    project = await factories.project(triage_lead_id=lead.id)
    release = await factories.release(project_id=project.id)
    bug = await factories.issue(project_id=project.id, release_id=release.id)
    return SimpleNamespace(
        users=users, lead=lead, project=project, release=release, bug=bug,
        client=client_for, admin=factories.admin_client, factories=factories,
    )


async def _as(world, role):
    return await world.client(world.users[role])


def _expect(role, allowed_roles, ok, *, support_status=404, other_status=403):
    if role in allowed_roles:
        return ok
    return support_status if role == "support" else other_status


# ── File a bug or task directly ───────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES)
async def test_file_item_directly(world, role):
    c = await _as(world, role)
    resp = await c.post("/issues", json={"title": "x", "project_id": world.project.id})
    assert resp.status_code == _expect(role, TECH, 201, support_status=403), resp.text


# ── View non-support items (and every item read path) ─────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES)
async def test_view_non_support_item(world, role):
    c = await _as(world, role)
    resp = await c.get(f"/issues/{world.bug.id}")
    assert resp.status_code == _expect(role, TECH, 200), resp.text


# ── Public comment / internal note ────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("internal", [False, True], ids=["public", "internal"])
@pytest.mark.parametrize("role", ROLES)
async def test_comment_on_non_support_item(world, role, internal):
    """Support has public comments in §7.3 — but only on items it can see, which
    this internally filed bug isn't, so it's a 404 either way."""
    c = await _as(world, role)
    resp = await c.post(
        f"/issues/{world.bug.id}/timeline", json={"body": "hello there", "is_internal": internal},
    )
    assert resp.status_code == _expect(role, TECH, 201), resp.text


# ── Triage ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES)
async def test_triage(world, role):
    c = await _as(world, role)
    resp = await c.post(
        f"/issues/{world.bug.id}/triage",
        json={"outcome": "accept", "assignee_id": world.users["qa"].id, "priority": "high"},
    )
    assert resp.status_code == _expect(role, TECH, 200), resp.text


# ── Be assigned work (BR-32) ──────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES)
async def test_be_assigned_work(world, role):
    resp = await world.admin.patch(
        f"/issues/{world.bug.id}", json={"assignee_id": world.users[role].id},
    )
    assert resp.status_code == _expect(role, TECH, 200, support_status=422), resp.text
    if role == "support":
        assert resp.json()["code"] == "not_assignable"


# ── Move items through workflow / verify a fix ────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES)
async def test_move_item_through_workflow(world, role):
    c = await _as(world, role)
    resp = await c.post(f"/issues/{world.bug.id}/transition", json={"to": "todo"})
    assert resp.status_code == _expect(role, TECH, 200), resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES)
async def test_verify_a_fix(world, role):
    resp = await world.admin.post(f"/issues/{world.bug.id}/transition", json={"to": "in_review"})
    assert resp.status_code == 200, resp.text
    c = await _as(world, role)
    resp = await c.post(f"/issues/{world.bug.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == _expect(role, TECH, 200), resp.text


# ── §9.2 flags ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES + ["triage_lead"])
async def test_flag_release_blocker(world, role):
    user = world.lead if role == "triage_lead" else world.users[role]
    c = await world.client(user)
    resp = await c.patch(f"/issues/{world.bug.id}", json={"is_release_blocker": True})
    allowed = {"qa", "product_manager", "cto", "admin", "triage_lead"}
    assert resp.status_code == _expect(role, allowed, 200), resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES + ["triage_lead"])
async def test_return_done_item(world, role):
    """08a: sending Done work back is every tech role's, never Support's."""
    await world.admin.post(f"/issues/{world.bug.id}/transition", json={"to": "done"})
    user = world.lead if role == "triage_lead" else world.users[role]
    c = await world.client(user)
    resp = await c.post(f"/issues/{world.bug.id}/returns", json={"comment": "Broken again"})
    allowed = TECH | {"triage_lead"}
    assert resp.status_code == _expect(role, allowed, 200), resp.text


# ── Manage releases (Dev only as the project's triage lead) ────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES + ["triage_lead"])
async def test_manage_releases(world, role):
    user = world.lead if role == "triage_lead" else world.users[role]
    c = await world.client(user)
    payload = {"project_id": world.project.id, "version": f"9.9-{role}"}
    resp = await c.post("/releases", json=payload)
    allowed = {"product_manager", "cto", "admin", "triage_lead"}
    assert resp.status_code == _expect(role, allowed, 201, support_status=403), resp.text
    if role == "developer":
        assert resp.json()["code"] == "not_triage_lead"


# ── Release go/no-go ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES)
async def test_release_go_nogo(world, role):
    c = await _as(world, role)
    resp = await c.post(f"/releases/{world.release.id}/approve")
    assert resp.status_code == _expect(role, {"cto", "admin"}, 200, support_status=403), resp.text


# ── Manage users and projects ─────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES)
async def test_manage_users(world, role):
    c = await _as(world, role)
    resp = await c.post("/team/invite", json={
        "name": "New Person", "username": f"new-{role}", "role": "qa",
        "temporary_password": "a-long-password-123",
    })
    assert resp.status_code == _expect(role, {"cto", "admin"}, 201, support_status=403), resp.text


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES)
async def test_manage_projects(world, role):
    c = await _as(world, role)
    resp = await c.post("/projects", json={
        "name": "P", "slug": f"p-{role}", "triage_lead_id": world.lead.id,
    })
    assert resp.status_code == _expect(role, {"cto", "admin"}, 201, support_status=403), resp.text


# ── Reports are tech-only (spec: Support gets 403 on reports) ────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ROLES)
async def test_reports(world, role):
    c = await _as(world, role)
    resp = await c.get("/reports/dashboard")
    assert resp.status_code == _expect(role, TECH, 200, support_status=403), resp.text
