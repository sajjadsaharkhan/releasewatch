"""Slice 04 (docs/phase-2/04-roles-and-visibility.md) — Support visibility, assignability,
triage-lead rules, and the ``allowed_actions`` / ``blocked_actions`` response contract.

Support sees only support-sourced items (BR-30). The rig files one through the
real slice-05 intake (``support_bug``) next to an internal bug and a task.
"""

import pytest


@pytest.fixture
async def rig(factories, client_for):
    support = await factories.user(role="support")
    qa = await factories.user(role="qa")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    bug = await factories.issue(
        project_id=project.id, release_id=release.id, title="Checkout crashes",
    )
    task = await factories.issue(project_id=project.id, type="task", title="Checkout refactor")
    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{bug.id}/timeline",
        json={"body": "Internal: root cause is the payment SDK.", "is_internal": True},
    )
    assert resp.status_code == 201
    resp = await admin.post(f"/issues/{bug.id}/timeline", json={"body": "Public: we're on it."})
    assert resp.status_code == 201
    support_client = await client_for(support)
    template = await factories.support_template(project_id=project.id)
    support_bug = await factories.support_report(
        support_client, template=template, title="Customer can't join class",
    )
    return {
        "support": support, "support_client": support_client, "support_bug": support_bug,
        "qa": qa, "qa_client": await client_for(qa),
        "project": project, "release": release, "bug": bug, "task": task, "admin": admin,
    }


# ── AC-08: tasks and internally filed bugs never reach Support ──────────────────


@pytest.mark.asyncio
async def test_ac_08_support_never_sees_tasks_or_internal_bugs(rig):
    c = rig["support_client"]
    listing = await c.get("/issues")
    assert listing.status_code == 200
    assert [i["id"] for i in listing.json()["items"]] == [rig["support_bug"].id]
    assert listing.json()["total"] == 1

    for iid in (rig["bug"].id, rig["task"].id):
        assert (await c.get(f"/issues/{iid}")).status_code == 404
        assert (await c.get(f"/issues/{iid}/timeline")).status_code == 404
        assert (await c.get(f"/issues/{iid}/attachments")).status_code == 404
    assert (await c.get(f"/issues/by-number/{rig['bug'].issue_number}")).status_code == 404
    adjacent = (await c.get(f"/issues/by-number/{rig['bug'].issue_number}/adjacent")).json()
    # The only neighbour Support can step to is its own report.
    assert adjacent == {"prev_number": None, "next_number": rig["support_bug"].issue_number}

    # Tech users still see both.
    qa_list = (await rig["qa_client"].get("/issues")).json()
    assert {i["id"] for i in qa_list["items"]} >= {rig["bug"].id, rig["task"].id}


@pytest.mark.asyncio
async def test_support_export_has_only_support_items(rig):
    resp = await rig["support_client"].get("/issues/export")
    assert resp.status_code == 200
    rows = resp.text.strip().splitlines()
    assert len(rows) == 2  # header + the support report
    assert "Customer can't join class" in rows[1]
    qa_rows = (await rig["qa_client"].get("/issues/export")).text.strip().splitlines()
    assert len(qa_rows) >= 4


@pytest.mark.asyncio
async def test_support_search_finds_nothing_internal(rig):
    params = {"q": "Checkout", "project_id": rig["project"].id}
    qa = (await rig["qa_client"].get("/search", params=params)).json()
    assert {r["issue_id"] for r in qa["results"]} >= {rig["bug"].id}
    support = (await rig["support_client"].get("/search", params=params)).json()
    assert support["results"] == []


@pytest.mark.asyncio
async def test_support_gets_403_on_reports_and_releases(rig):
    c = rig["support_client"]
    assert (await c.get("/reports/dashboard")).status_code == 403
    assert (await c.get(f"/reports/releases/{rig['release'].id}")).status_code == 403
    assert (await c.get("/releases")).status_code == 403


# ── Inbox + WebSocket: nothing about invisible items ─────────────────────────────


@pytest.fixture
def pushes(monkeypatch):
    sent: list[tuple[str, dict]] = []

    async def _publish(channel, data):
        sent.append((channel, data))

    import app.core.redis_client as rc
    monkeypatch.setattr(rc, "publish", _publish)
    return sent


@pytest.mark.asyncio
async def test_support_inbox_and_ws_skip_invisible_items(rig, pushes, telegram):
    await telegram.link_telegram(rig["support"])
    resp = await rig["admin"].post(
        f"/issues/{rig['bug'].id}/timeline",
        json={
            "body": f"@{rig['support'].username} @{rig['qa'].username} have a look",
            "mentioned_user_ids": [rig["support"].id, rig["qa"].id],
        },
    )
    assert resp.status_code == 201

    support_inbox = (await rig["support_client"].get("/inbox")).json()
    assert support_inbox["items"] == [] and support_inbox["unreadCount"] == 0
    assert (await rig["support_client"].get("/inbox/unread-count")).json()["unreadCount"] == 0
    qa_inbox = (await rig["qa_client"].get("/inbox")).json()
    assert [i["type"] for i in qa_inbox["items"]] == ["mention"]

    channels = [ch for ch, _ in pushes]
    assert f"rw:inbox:{rig['qa'].id}" in channels
    assert f"rw:inbox:{rig['support'].id}" not in channels
    assert telegram.sent_to(rig["support"]) == []


# ── AC-07: internal notes never reach Support, on items it can see ──────────────


@pytest.mark.asyncio
async def test_ac_07_support_never_sees_internal_notes(rig, pushes):
    c = rig["support_client"]
    bug_id = rig["support_bug"].id
    admin = rig["admin"]
    resp = await admin.post(
        f"/issues/{bug_id}/timeline",
        json={"body": "Internal: root cause is the payment SDK.", "is_internal": True},
    )
    assert resp.status_code == 201
    resp = await admin.post(f"/issues/{bug_id}/timeline", json={"body": "Public: we're on it."})
    assert resp.status_code == 201
    # The public comment notified the reporter; only count what arrives from here on.
    before = {i["id"] for i in (await c.get("/inbox")).json()["items"]}
    pushes.clear()

    async def new_inbox():
        return [i for i in (await c.get("/inbox")).json()["items"] if i["id"] not in before]

    timeline = (await c.get(f"/issues/{bug_id}/timeline")).json()
    bodies = [e["body"] for e in timeline["items"]]
    assert "Public: we're on it." in bodies
    assert not any("Internal" in (b or "") for b in bodies)
    assert all(not e["is_internal"] for e in timeline["items"])
    # Counts exclude internal notes too.
    tech_total = (await rig["qa_client"].get(f"/issues/{bug_id}/timeline")).json()["total"]
    assert timeline["total"] == tech_total - 1

    # An internal note mentioning Support creates no inbox row or push for them.
    resp = await rig["admin"].post(
        f"/issues/{bug_id}/timeline",
        json={
            "body": "Internal ping", "is_internal": True,
            "mentioned_user_ids": [rig["support"].id],
        },
    )
    internal_id = resp.json()["id"]
    assert await new_inbox() == []
    assert f"rw:inbox:{rig['support'].id}" not in [ch for ch, _ in pushes]

    # …while a public one does (a mention is one of the few things Support is
    # notified of — slice 06, 2026-09-24 decision).
    await rig["admin"].post(
        f"/issues/{bug_id}/timeline",
        json={"body": "Public ping", "mentioned_user_ids": [rig["support"].id]},
    )
    assert [i["type"] for i in await new_inbox()] == ["mention"]

    # Support can't touch the internal note either — it doesn't exist for them.
    edited = await c.patch(f"/issues/{bug_id}/timeline/{internal_id}", json={"body": "x"})
    assert edited.status_code == 404
    reacted = await c.post(
        f"/issues/{bug_id}/timeline/{internal_id}/reactions", json={"emoji_key": "thumbs_up"},
    )
    assert reacted.status_code == 404

    # Support may comment publicly but never post an internal note.
    public = await c.post(f"/issues/{bug_id}/timeline", json={"body": "Customer says hi"})
    assert public.status_code == 201
    internal = await c.post(
        f"/issues/{bug_id}/timeline", json={"body": "sneaky", "is_internal": True},
    )
    assert internal.status_code == 403


@pytest.mark.asyncio
async def test_support_item_response_hides_tech_actions(rig):
    item = (await rig["support_client"].get(f"/issues/{rig['support_bug'].id}")).json()
    assert set(item["allowed_actions"]) == {"comment_public", "report_recurrence"}
    assert item["blocked_actions"] == []
    assert item["allowed_transitions"] == [] and item["blocked_transitions"] == []


# ── allowed_actions / blocked_actions for tech users ────────────────────────────


@pytest.mark.asyncio
async def test_developer_sees_flags_disabled_with_reason(factories, client_for, rig):
    dev = await factories.user(role="developer")
    item = (await (await client_for(dev)).get(f"/issues/{rig['bug'].id}")).json()
    assert "comment_internal" in item["allowed_actions"]
    assert "transition:in_progress" in item["allowed_actions"]
    blocked = {b["action"]: b for b in item["blocked_actions"]}
    assert blocked["flag_regression"]["code"] == "not_triage_lead"
    assert blocked["flag_regression"]["detail"]
    assert "in_progress" in item["allowed_transitions"]


@pytest.mark.asyncio
async def test_self_verification_is_still_allowed(factories, client_for, rig):
    """Regression guard for the 2026-09-22 decision: Policy must not bring AC-27 back."""
    dev = await factories.user(role="developer")
    c = await client_for(dev)
    bug_id = rig["bug"].id
    for to in ("in_progress", "in_review"):
        assert (await c.post(f"/issues/{bug_id}/transition", json={"to": to})).status_code == 200
    resp = await c.post(f"/issues/{bug_id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "done"


# ── AC-47: Support is never assignable ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_47_support_not_assignable(rig):
    admin = rig["admin"]
    picker = (await admin.get("/team", params={"assignable": "true"})).json()
    roles = {u["role"] for u in picker}
    ids = {u["id"] for u in picker}
    assert "support" not in roles and rig["support"].id not in ids and rig["qa"].id in ids
    # Without the flag the plain team list still includes Support (mentions, Settings).
    assert rig["support"].id in {u["id"] for u in (await admin.get("/team")).json()}

    sid, bug_id = rig["support"].id, rig["bug"].id
    for method, url, body in [
        ("patch", f"/issues/{bug_id}", {"assignee_id": sid}),
        ("post", f"/issues/{bug_id}/triage", {"outcome": "accept", "assignee_id": sid, "priority": "low"}),
        ("post", "/issues", {"title": "t", "project_id": rig["project"].id, "assignee_id": sid}),
    ]:
        resp = await getattr(admin, method)(url, json=body)
        assert resp.status_code == 422, (url, resp.text)
        assert resp.json()["code"] == "not_assignable"


# ── Triage lead: required, flagged, and admins stand in (BR-15, AC-23) ───────────


@pytest.mark.asyncio
async def test_project_requires_an_active_tech_triage_lead(factories, rig):
    admin = rig["admin"]
    base = {"name": "P"}
    missing = await admin.post("/projects", json={**base, "slug": "no-lead"})
    assert missing.status_code == 422 and missing.json()["code"] == "triage_lead_required"
    support_lead = await admin.post(
        "/projects", json={**base, "slug": "support-lead", "triage_lead_id": rig["support"].id},
    )
    assert support_lead.status_code == 422 and support_lead.json()["code"] == "invalid_triage_lead"
    cleared = await admin.patch(f"/projects/{rig['project'].slug}", json={"triage_lead_id": None})
    assert cleared.status_code == 422
    slug = rig["project"].slug
    ok = await admin.patch(f"/projects/{slug}", json={"triage_lead_id": rig["qa"].id})
    assert ok.status_code == 200 and ok.json()["needs_triage_lead"] is False


@pytest.mark.asyncio
async def test_ac_23_deactivated_triage_lead_flags_project_and_notifies_admins(
    factories, client_for, telegram,
):
    lead = await factories.user(role="developer")
    other_admin = await factories.user(role="admin")
    await telegram.link_telegram(other_admin)
    project = await factories.project(triage_lead_id=lead.id)
    admin = factories.admin_client

    impact = (await admin.get(f"/team/{lead.id}/deactivation-impact")).json()
    assert [p["id"] for p in impact["affected_projects"]] == [project.id]

    resp = await admin.patch(f"/team/{lead.id}/deactivate")
    assert resp.status_code == 200
    assert [p["slug"] for p in resp.json()["affected_projects"]] == [project.slug]

    flagged = (await admin.get(f"/projects/{project.slug}")).json()
    assert flagged["needs_triage_lead"] is True and flagged["needsTriageLead"] is True
    listed = {p["id"]: p for p in (await admin.get("/projects")).json()}
    assert listed[project.id]["needs_triage_lead"] is True

    # A new bug's triage notification goes to every active admin until a lead is set.
    qa = await factories.user(role="qa")
    await factories.issue(project_id=project.id, client=await client_for(qa))
    other_admin_inbox = (await (await client_for(other_admin)).get("/inbox")).json()
    assert "filed" in [i["type"] for i in other_admin_inbox["items"]]
    assert [t for t, _ in telegram.sent_to(other_admin)] == ["filed"]
