"""Slice 05 (docs/phase-2/05-support-intake.md) — support templates, report intake,
and the Support reports list. Every assertion goes through the API.
"""

import pytest

pytestmark = pytest.mark.asyncio

ONLINE_CLASS_FIELDS = [
    {"label": "Class time", "field_type": "datetime", "is_required": True,
     "help_text": "When the class started, in your local time."},
    {"label": "Class name", "field_type": "short_text", "is_required": True},
    {"label": "Platform", "field_type": "single_select", "is_required": False,
     "options": [{"value": "web", "label": "Web app"}, {"value": "ios", "label": "iOS app"}]},
    {"label": "Customer ID", "field_type": "number", "is_required": False},
]


def _ids(template) -> dict[str, str]:
    """Label → field id (as the string key the API expects)."""
    return {f["label"]: str(f["id"]) for f in template.fields}


@pytest.fixture
async def rig(factories, client_for):
    lead = await factories.user(role="developer")
    support = await factories.user(role="support")
    project = await factories.project(triage_lead_id=lead.id)
    template = await factories.support_template(
        project_id=project.id, name="Online class problem", fields=ONLINE_CLASS_FIELDS,
    )
    return {
        "lead": lead, "lead_client": await client_for(lead),
        "support": support, "support_client": await client_for(support),
        "project": project, "template": template, "admin": factories.admin_client,
    }


# ── AC-01 ────────────────────────────────────────────────────────────────────


async def test_ac_01_project_without_active_template_hidden(factories, rig):
    c = rig["support_client"]
    no_template = await factories.project()
    only_inactive = await factories.project()
    t = await factories.support_template(project_id=only_inactive.id)
    await rig["admin"].post(f"/projects/{only_inactive.id}/templates/{t.id}/deactivate")
    archived = await factories.project()
    await factories.support_template(project_id=archived.id)
    assert (await rig["admin"].delete(f"/projects/{archived.slug}")).status_code == 204

    projects = (await c.get("/support/projects")).json()
    assert [p["id"] for p in projects] == [rig["project"].id]
    assert no_template.id not in [p["id"] for p in projects]

    templates = (await c.get(f"/support/projects/{only_inactive.id}/templates")).json()
    assert templates == []
    active = (await c.get(f"/support/projects/{rig['project'].id}/templates")).json()
    assert [t["name"] for t in active] == ["Online class problem"]
    assert [f["label"] for f in active[0]["fields"]] == [f["label"] for f in ONLINE_CLASS_FIELDS]
    assert active[0]["fields"][0]["help_text"] == "When the class started, in your local time."


# ── AC-02 ────────────────────────────────────────────────────────────────────


async def test_ac_02_required_field_blocks_submit(rig):
    c = rig["support_client"]
    ids = _ids(rig["template"])
    resp = await c.post("/support/reports", json={
        "template_id": rig["template"].id,
        "title": "Can't join",
        "values": {ids["Class name"]: "  "},
    })
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "invalid_fields"
    assert set(body["errors"]) == {ids["Class time"], ids["Class name"]}

    # Nothing was filed.
    assert (await c.get("/support/reports")).json()["total"] == 0


async def test_title_is_required(rig):
    ids = _ids(rig["template"])
    resp = await rig["support_client"].post("/support/reports", json={
        "template_id": rig["template"].id, "title": "",
        "values": {ids["Class time"]: "2026-09-21T18:00", ids["Class name"]: "IELTS"},
    })
    assert resp.status_code == 422


# ── AC-03 ────────────────────────────────────────────────────────────────────


async def test_ac_03_submission_composes_description_in_template_order(rig, telegram):
    await telegram.link_telegram(rig["lead"])
    ids = _ids(rig["template"])
    # Values sent in reverse order — the description follows the template order.
    values = {
        ids["Customer ID"]: "48213",
        ids["Platform"]: "ios",
        ids["Class name"]: "IELTS B2 — Evening",
        ids["Class time"]: "2026-09-21T18:00",
    }
    resp = await rig["support_client"].post("/support/reports", json={
        "template_id": rig["template"].id,
        "title": "Student can't join class",
        "values": values,
        "description": "The student sees a blank screen.",
    })
    assert resp.status_code == 201, resp.text
    report = resp.json()
    assert report["status"] == "new"
    assert report["key"].startswith("BUG-")
    assert report["recurrence_count"] == 1

    item = (await rig["lead_client"].get(f"/issues/{report['id']}")).json()
    assert item["type"] == "bug"
    assert item["source"] == "support"
    assert item["status"] == "new"
    assert item["priority"] is None
    assert item["project_id"] == rig["project"].id
    assert item["description"] == (
        "**Report template:** Online class problem\n\n"
        "- **Class time:** 2026-09-21 18:00\n"
        "- **Class name:** IELTS B2 — Evening\n"
        "- **Platform:** iOS app\n"
        "- **Customer ID:** 48213\n\n"
        "---\n\n"
        "The student sees a blank screen."
    )

    # It lands in the triage queue, and the lead hears about it (story 21).
    queue = (await rig["lead_client"].get(
        "/issues", params={"project_id": rig["project"].id, "statuses": "new,needs_info"},
    )).json()
    assert [i["id"] for i in queue["items"]] == [report["id"]]
    lead_inbox = (await rig["lead_client"].get("/inbox")).json()["items"]
    assert [i["type"] for i in lead_inbox] == ["filed"]
    sent = telegram.sent_to(rig["lead"])
    assert [tpl for tpl, _ in sent] == ["support_report_filed"]
    assert sent[0][1]["project_name"] == rig["project"].name


async def test_empty_optional_fields_and_description_are_omitted(rig):
    ids = _ids(rig["template"])
    report = await _submit(rig, {ids["Class time"]: "2026-09-21T18:00", ids["Class name"]: "IELTS",
                                 ids["Platform"]: "", ids["Customer ID"]: None})
    item = (await rig["lead_client"].get(f"/issues/{report['id']}")).json()
    assert item["description"] == (
        "**Report template:** Online class problem\n\n"
        "- **Class time:** 2026-09-21 18:00\n"
        "- **Class name:** IELTS"
    )


async def test_markdown_in_values_is_escaped(rig):
    ids = _ids(rig["template"])
    report = await _submit(rig, {
        ids["Class time"]: "2026-09-21T18:00",
        ids["Class name"]: "**Bold** [link](http://x.io) @admin\n- not a list",
    })
    item = (await rig["lead_client"].get(f"/issues/{report['id']}")).json()
    assert (
        "- **Class name:** \\*\\*Bold\\*\\* \\[link\\]\\(http://x.io\\) \\@admin - not a list"
        in item["description"]
    )


async def _submit(rig, values, *, template=None, description=None):
    resp = await rig["support_client"].post("/support/reports", json={
        "template_id": (template or rig["template"]).id,
        "title": "A report",
        "values": values,
        "description": description,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Field types: valid and invalid (story 14) ────────────────────────────────


@pytest.mark.parametrize(
    ("field_type", "valid", "rendered", "invalid"),
    [
        ("short_text", "Evening group", "Evening group", 42),
        ("long_text", "Line one\nLine two", "- **Value:**\n> Line one\n> Line two", 7),
        ("number", "12.50", "12.5", "twelve"),
        ("number", 7, "7", True),
        ("date", "2026-09-21", "2026-09-21", "21/09/2026"),
        ("datetime", "2026-09-21T18:05:33", "2026-09-21 18:05", "tomorrow evening"),
        ("url", "https://meet.example.com/abc", "https://meet.example.com/abc", "meet.example.com"),
        ("single_select", "b", "Option B", "c"),
    ],
)
async def test_field_types(factories, rig, field_type, valid, rendered, invalid):
    field = {"label": "Value", "field_type": field_type, "is_required": True}
    if field_type == "single_select":
        field["options"] = [
            {"value": "a", "label": "Option A"}, {"value": "b", "label": "Option B"},
        ]
    template = await factories.support_template(
        project_id=rig["project"].id, name=f"Typed {field_type} {valid!r}", fields=[field],
    )
    fid = str(template.fields[0]["id"])

    bad = await rig["support_client"].post("/support/reports", json={
        "template_id": template.id, "title": "Typed", "values": {fid: invalid},
    })
    assert bad.status_code == 422
    assert list(bad.json()["errors"]) == [fid]

    report = await _submit(rig, {fid: valid}, template=template)
    description = (await rig["lead_client"].get(f"/issues/{report['id']}")).json()["description"]
    if field_type == "long_text":
        assert rendered in description
    else:
        assert f"- **Value:** {rendered}" in description


# ── AC-04 / AC-05 / AC-06 ─────────────────────────────────────────────────────


async def test_ac_04_template_edit_does_not_change_existing_items(rig):
    ids = _ids(rig["template"])
    report = await _submit(rig, {ids["Class time"]: "2026-09-21T18:00", ids["Class name"]: "IELTS"})
    before = (await rig["lead_client"].get(f"/issues/{report['id']}")).json()["description"]

    admin = rig["admin"]
    pid, tid = rig["project"].id, rig["template"].id
    renamed = await admin.patch(f"/projects/{pid}/templates/{tid}", json={"name": "Class issue"})
    assert renamed.status_code == 200
    resp = await admin.put(f"/projects/{pid}/templates/{tid}/fields", json=[
        {"id": int(ids["Class name"]), "label": "Course", "field_type": "short_text",
         "is_required": True},
    ])
    assert resp.status_code == 200, resp.text
    assert (await admin.post(f"/projects/{pid}/templates/{tid}/deactivate")).status_code == 200

    after = (await rig["lead_client"].get(f"/issues/{report['id']}")).json()["description"]
    assert after == before


async def test_ac_05_inactive_template_rejected_on_submit(rig):
    ids = _ids(rig["template"])
    pid, tid = rig["project"].id, rig["template"].id
    await rig["admin"].post(f"/projects/{pid}/templates/{tid}/deactivate")
    resp = await rig["support_client"].post("/support/reports", json={
        "template_id": tid, "title": "Late",
        "values": {ids["Class time"]: "2026-09-21T18:00", ids["Class name"]: "IELTS"},
    })
    assert resp.status_code == 409
    assert resp.json()["code"] == "template_inactive"

    # Reactivating brings it back.
    await rig["admin"].post(f"/projects/{pid}/templates/{tid}/activate")
    resp = await rig["support_client"].post("/support/reports", json={
        "template_id": tid, "title": "Late",
        "values": {ids["Class time"]: "2026-09-21T18:00", ids["Class name"]: "IELTS"},
    })
    assert resp.status_code == 201


async def test_ac_06_reports_remain_visible_after_last_template_deactivated(rig):
    ids = _ids(rig["template"])
    report = await _submit(rig, {ids["Class time"]: "2026-09-21T18:00", ids["Class name"]: "IELTS"})
    pid, tid = rig["project"].id, rig["template"].id
    await rig["admin"].post(f"/projects/{pid}/templates/{tid}/deactivate")

    c = rig["support_client"]
    assert (await c.get("/support/projects")).json() == []
    listing = (await c.get("/support/reports")).json()
    assert [r["id"] for r in listing["items"]] == [report["id"]]
    assert (await c.get(f"/issues/{report['id']}")).status_code == 200


# ── Support reports list (FR-11) ─────────────────────────────────────────────


async def test_support_reports_list_search_and_filters(factories, rig):
    ids = _ids(rig["template"])
    base = {ids["Class time"]: "2026-09-21T18:00", ids["Class name"]: "IELTS"}
    first = await _submit(rig, base)
    other_project = await factories.project()
    other_template = await factories.support_template(project_id=other_project.id)
    second = (await factories.support_report(
        rig["support_client"], template=other_template, title="Payment failed twice",
    )).__dict__
    internal = await factories.issue(project_id=rig["project"].id, title="Payment refactor")
    # Move the first report out of New.
    resp = await rig["lead_client"].post(
        f"/issues/{first['id']}/transition", json={"to": "needs_info"},
    )
    assert resp.status_code == 200, resp.text

    c = rig["support_client"]
    everything = (await c.get("/support/reports")).json()
    assert {r["id"] for r in everything["items"]} == {first["id"], second["id"]}
    assert everything["total"] == 2
    row = next(r for r in everything["items"] if r["id"] == second["id"])
    assert row["project_name"] == other_project.name and row["recurrence_count"] == 1

    by_text = (await c.get("/support/reports", params={"q": "payment"})).json()
    assert [r["id"] for r in by_text["items"]] == [second["id"]]
    by_project = (await c.get("/support/reports", params={"project_id": rig["project"].id})).json()
    assert [r["id"] for r in by_project["items"]] == [first["id"]]
    statuses = [("status", "needs_info"), ("status", "done")]
    by_status = (await c.get("/support/reports", params=statuses)).json()
    assert [r["id"] for r in by_status["items"]] == [first["id"]]

    # Tech users can open the list too; internal items never appear in it.
    tech = (await rig["lead_client"].get("/support/reports")).json()
    assert internal.id not in {r["id"] for r in tech["items"]}
    assert tech["total"] == 2


# ── Permissions ───────────────────────────────────────────────────────────────


async def test_support_gets_403_on_template_admin(rig):
    c = rig["support_client"]
    pid, tid = rig["project"].id, rig["template"].id
    assert (await c.get(f"/projects/{pid}/templates")).status_code == 403
    assert (await c.post(f"/projects/{pid}/templates", json={"name": "x"})).status_code == 403
    renamed = await c.patch(f"/projects/{pid}/templates/{tid}", json={"name": "x"})
    assert renamed.status_code == 403
    assert (await c.put(f"/projects/{pid}/templates/{tid}/fields", json=[])).status_code == 403
    assert (await c.post(f"/projects/{pid}/templates/{tid}/deactivate")).status_code == 403
    assert (await c.post(f"/projects/{pid}/templates/{tid}/activate")).status_code == 403


async def test_template_admin_is_cto_and_admin_only(factories, client_for, rig):
    pid = rig["project"].id
    cto = await client_for(await factories.user(role="cto"))
    resp = await cto.post(f"/projects/{pid}/templates", json={"name": "Payment problem"})
    assert resp.status_code == 201
    for role in ("developer", "qa", "pm"):
        c = await client_for(await factories.user(role=role))
        assert (await c.get(f"/projects/{pid}/templates")).status_code == 403


async def test_only_support_and_admin_submit_reports(factories, client_for, rig):
    dev = await client_for(await factories.user(role="developer"))
    assert (await dev.get("/support/projects")).status_code == 403
    ids = _ids(rig["template"])
    resp = await dev.post("/support/reports", json={
        "template_id": rig["template"].id, "title": "x",
        "values": {ids["Class time"]: "2026-09-21T18:00", ids["Class name"]: "IELTS"},
    })
    assert resp.status_code == 403


# ── Template admin behaviour ──────────────────────────────────────────────────


async def test_fields_reorder_keeps_ids_and_inactive_templates_are_listed(rig):
    admin = rig["admin"]
    pid, tid = rig["project"].id, rig["template"].id
    fields = rig["template"].fields
    reordered = [fields[3], fields[0], fields[2], fields[1]]
    resp = await admin.put(f"/projects/{pid}/templates/{tid}/fields", json=[
        {k: f[k] for k in ("id", "label", "field_type", "is_required", "help_text", "options")}
        for f in reordered
    ])
    assert resp.status_code == 200, resp.text
    out = resp.json()["fields"]
    assert [f["id"] for f in out] == [f["id"] for f in reordered]
    assert [f["position"] for f in out] == [0, 1, 2, 3]

    await admin.post(f"/projects/{pid}/templates/{tid}/deactivate")
    listed = (await admin.get(f"/projects/{pid}/templates")).json()
    assert [(t["id"], t["is_active"]) for t in listed] == [(tid, False)]


async def test_template_validation(rig):
    admin = rig["admin"]
    pid = rig["project"].id
    dup = await admin.post(f"/projects/{pid}/templates", json={"name": "online class problem"})
    assert dup.status_code == 409 and dup.json()["code"] == "template_name_taken"
    no_options = await admin.post(f"/projects/{pid}/templates", json={
        "name": "Select without options",
        "fields": [{"label": "Pick", "field_type": "single_select"}],
    })
    assert no_options.status_code == 422
    same_label = await admin.post(f"/projects/{pid}/templates", json={
        "name": "Twice", "fields": [
            {"label": "Name", "field_type": "short_text"},
            {"label": "name", "field_type": "long_text"},
        ],
    })
    assert same_label.status_code == 422 and same_label.json()["code"] == "duplicate_field_label"


async def test_project_list_carries_template_counts(factories, rig):
    extra = await factories.support_template(project_id=rig["project"].id, name="Payment problem")
    await rig["admin"].post(f"/projects/{rig['project'].id}/templates/{extra.id}/deactivate")
    projects = {p["id"]: p for p in (await rig["admin"].get("/projects")).json()}
    mine = projects[rig["project"].id]
    assert (mine["support_template_count"], mine["active_support_template_count"]) == (2, 1)
    bare = await factories.project()
    projects = {p["id"]: p for p in (await rig["admin"].get("/projects")).json()}
    assert projects[bare.id]["support_template_count"] == 0


async def test_template_can_be_created_switched_off(rig):
    resp = await rig["admin"].post(
        f"/projects/{rig['project'].id}/templates", json={"name": "Draft", "is_active": False},
    )
    assert resp.status_code == 201 and resp.json()["is_active"] is False
    names = [t["name"] for t in (await rig["support_client"].get(
        f"/support/projects/{rig['project'].id}/templates")).json()]
    assert "Draft" not in names


async def test_support_reports_list_shows_assignee(factories, rig):
    ids = _ids(rig["template"])
    report = await _submit(rig, {ids["Class time"]: "2026-09-21T18:00", ids["Class name"]: "IELTS"})
    row = (await rig["support_client"].get("/support/reports")).json()["items"][0]
    assert row["assignee_user"] is None
    dev = await factories.user(role="developer")
    resp = await rig["admin"].patch(f"/issues/{report['id']}", json={"assignee_id": dev.id})
    assert resp.status_code == 200, resp.text
    row = (await rig["support_client"].get("/support/reports")).json()["items"][0]
    assert row["assignee_user"]["id"] == dev.id
    assert row["assignee_user"]["username"] == dev.username
