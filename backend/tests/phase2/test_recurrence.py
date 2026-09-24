"""Slice 07 — Report recurrence.

docs/phase-2/07-recurrence.md (FR-13–16, BR-22/23, BR-50, AC-09–13).
Observations go through HTTP responses, each recipient's ``GET /inbox``, and
the Telegram recorder.
"""

import asyncio

import pytest
import pytest_asyncio

FR_16 = (
    "Fixed items can't take a recurrence. File a new report; "
    "triage will merge it into this item as a regression."
)


@pytest_asyncio.fixture
async def rig(factories, client_for):
    lead = await factories.user(role="developer", name="Lead Dev")
    developer = await factories.user(role="developer")
    qa = await factories.user(role="qa")
    support = await factories.user(role="support")
    other_support = await factories.user(role="support")
    project = await factories.project(triage_lead_id=lead.id)
    template = await factories.support_template(project_id=project.id)
    return {
        "admin": factories.admin_client,
        "lead": lead, "lead_client": await client_for(lead),
        "developer": developer, "dev_client": await client_for(developer),
        "qa": qa, "qa_client": await client_for(qa),
        "support": support, "support_client": await client_for(support),
        "other_support": other_support, "other_support_client": await client_for(other_support),
        "project": project,
        "template": template,
    }


async def support_report(factories, rig, client=None):
    return await factories.support_report(client or rig["support_client"], template=rig["template"])


async def recur(client, issue_id, comment="Customer #42 hit it too.", **body):
    return await client.post(f"/issues/{issue_id}/recurrences", json={"comment": comment, **body})


async def get(client, issue_id) -> dict:
    return (await client.get(f"/issues/{issue_id}")).json()


async def timeline(client, issue_id) -> list[dict]:
    return (await client.get(f"/issues/{issue_id}/timeline", params={"size": 200})).json()["items"]


async def inbox(client) -> list[dict]:
    return (await client.get("/inbox", params={"size": 100})).json()["items"]


async def inbox_types(client) -> list[str]:
    return [i["type"] for i in await inbox(client)]


async def to_status(client, issue_id, to, **extra):
    resp = await client.post(f"/issues/{issue_id}/transition", json={"to": to, **extra})
    assert resp.status_code == 200, resp.text
    return resp.json()


def blocked(issue: dict, action: str) -> dict | None:
    return next((b for b in issue["blocked_actions"] if b["action"] == action), None)


# ── AC-09 — a comment is required ────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("comment", ["", "   \n\t "])
async def test_ac_09_recurrence_requires_comment(factories, rig, comment):
    bug = await support_report(factories, rig)
    resp = await recur(rig["support_client"], bug.id, comment=comment)
    assert resp.status_code == 422
    assert (await get(rig["admin"], bug.id))["recurrence_count"] == 1


@pytest.mark.asyncio
async def test_recurrence_requires_comment_field(factories, rig):
    bug = await support_report(factories, rig)
    resp = await rig["support_client"].post(f"/issues/{bug.id}/recurrences", json={})
    assert resp.status_code == 422


# ── AC-10 — +1 and a timeline comment ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_10_recurrence_increments_and_adds_timeline_comment(factories, rig):
    bug = await support_report(factories, rig)
    assert bug.recurrence_count == 1

    resp = await recur(rig["support_client"], bug.id, comment="  Second customer: order 991.  ")
    assert resp.status_code == 201, resp.text
    assert resp.json()["recurrence_count"] == 2

    resp = await recur(rig["dev_client"], bug.id, comment="Heard from sales too.")
    assert resp.status_code == 201, resp.text
    assert resp.json()["recurrence_count"] == 3

    events = [e for e in await timeline(rig["support_client"], bug.id) if e["event_type"] == "recurrence"]
    assert [e["body"] for e in events] == ["Second customer: order 991.", "Heard from sales too."]
    assert [e["meta"]["recurrence_count"] for e in events] == [2, 3]
    assert all(e["is_internal"] is False for e in events)
    assert [e["actor_id"] for e in events] == [rig["support"].id, rig["developer"].id]
    # The comment is the recurrence event itself — not credited, not duplicated.
    assert not any(e["event_type"] == "comment" for e in await timeline(rig["admin"], bug.id))


@pytest.mark.asyncio
async def test_every_role_can_report_recurrence(factories, rig):
    bug = await support_report(factories, rig)
    for client in ("support_client", "qa_client", "dev_client", "lead_client", "admin"):
        assert (await recur(rig[client], bug.id)).status_code == 201
    assert (await get(rig["admin"], bug.id))["recurrence_count"] == 6


@pytest.mark.asyncio
async def test_recurrence_on_open_bug_notifies_assignee_and_reporter(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, client=rig["qa_client"])
    await rig["lead_client"].post(
        f"/issues/{bug.id}/triage",
        json={"outcome": "accept", "priority": "high", "assignee_id": rig["developer"].id},
    )
    assert (await recur(rig["admin"], bug.id)).status_code == 201

    assert "comment" in await inbox_types(rig["dev_client"])
    assert "comment" in await inbox_types(rig["qa_client"])
    assert "recurrence_on_cancelled" not in await inbox_types(rig["lead_client"])


@pytest.mark.asyncio
async def test_recurrence_attaches_pending_uploads(factories, rig):
    bug = await support_report(factories, rig)
    resp = await recur(rig["support_client"], bug.id, pending_attachments=[{
        "s3_key": "pending/abc/screenshot.png",
        "filename": "screenshot.png",
        "mime_type": "image/png",
        "file_size_bytes": 1234,
        "attachment_type": "screenshot",
    }])
    assert resp.status_code == 201, resp.text
    files = (await rig["support_client"].get(f"/issues/{bug.id}/attachments")).json()
    assert [f["file_name"] for f in files] == ["screenshot.png"]


# ── Subscription (FR-14) ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recurrence_reporter_gets_support_done(factories, rig, telegram):
    bug = await support_report(factories, rig)
    await rig["lead_client"].post(f"/issues/{bug.id}/triage", json={"outcome": "accept", "priority": "high"})
    await telegram.link_telegram(rig["other_support"])

    assert (await recur(rig["other_support_client"], bug.id)).status_code == 201
    # Support hears nothing from the recurrence itself (§13).
    assert await inbox_types(rig["other_support_client"]) == []

    await to_status(rig["admin"], bug.id, "done")
    assert await inbox_types(rig["other_support_client"]) == ["support_done"]
    assert [t for t, _ in telegram.sent_to(rig["other_support"])] == ["support_done"]


@pytest.mark.asyncio
async def test_already_subscribed_reporter_is_not_duplicated(factories, rig):
    bug = await support_report(factories, rig)
    assert (await recur(rig["support_client"], bug.id)).status_code == 201
    await rig["lead_client"].post(f"/issues/{bug.id}/triage", json={"outcome": "accept", "priority": "high"})
    await to_status(rig["admin"], bug.id, "done")
    assert await inbox_types(rig["support_client"]) == ["support_done"]


# ── AC-11 — Cancelled bug: lead notified, stays Cancelled ────────────────────


@pytest.mark.asyncio
async def test_ac_11_recurrence_on_cancelled_notifies_lead_stays_cancelled(factories, rig, telegram):
    bug = await support_report(factories, rig)
    await rig["lead_client"].post(
        f"/issues/{bug.id}/triage", json={"outcome": "reject", "reason": "cannot_reproduce"},
    )
    await telegram.link_telegram(rig["lead"])

    resp = await recur(rig["other_support_client"], bug.id)
    assert resp.status_code == 201, resp.text
    after = resp.json()
    assert after["status"] == "cancelled"
    assert after["cancel_reason"] == "cannot_reproduce"
    assert after["recurrence_count"] == 2
    assert "recurrence_on_cancelled" in await inbox_types(rig["lead_client"])
    assert "recurrence_on_cancelled" in [t for t, _ in telegram.sent_to(rig["lead"])]


@pytest.mark.asyncio
async def test_recurrence_on_cancelled_without_lead_goes_to_admins(factories, rig, db_session):
    from sqlalchemy import update

    from app.db.models.project import Project

    bug = await support_report(factories, rig)
    await rig["lead_client"].post(
        f"/issues/{bug.id}/triage", json={"outcome": "reject", "reason": "expected_behavior"},
    )
    # BR-15 forbids clearing the lead through the API; simulate a deactivated lead.
    await db_session.execute(update(Project).where(Project.id == rig["project"].id).values(triage_lead_id=None))
    await db_session.commit()

    assert (await recur(rig["support_client"], bug.id)).status_code == 201
    assert "recurrence_on_cancelled" in await inbox_types(rig["admin"])
    assert "recurrence_on_cancelled" not in await inbox_types(rig["lead_client"])


# ── AC-12 — Done bug: refused with guidance ──────────────────────────────────


@pytest.mark.asyncio
async def test_ac_12_recurrence_blocked_on_done_with_guidance(factories, rig):
    bug = await support_report(factories, rig)
    await rig["lead_client"].post(f"/issues/{bug.id}/triage", json={"outcome": "accept", "priority": "high"})
    await to_status(rig["admin"], bug.id, "done")

    resp = await recur(rig["support_client"], bug.id)
    assert resp.status_code == 409
    assert resp.json()["code"] == "recurrence_on_done"
    assert resp.json()["detail"] == FR_16
    assert (await get(rig["admin"], bug.id))["recurrence_count"] == 1

    # The UI takes the disabled state and its text from the API.
    issue = await get(rig["support_client"], bug.id)
    assert "report_recurrence" not in issue["allowed_actions"]
    assert blocked(issue, "report_recurrence") == {
        "action": "report_recurrence", "code": "recurrence_on_done", "detail": FR_16,
    }


@pytest.mark.asyncio
async def test_open_and_cancelled_bugs_allow_recurrence_in_actions(factories, rig):
    bug = await support_report(factories, rig)
    assert "report_recurrence" in (await get(rig["support_client"], bug.id))["allowed_actions"]
    await rig["lead_client"].post(
        f"/issues/{bug.id}/triage", json={"outcome": "reject", "reason": "user_error"},
    )
    assert "report_recurrence" in (await get(rig["support_client"], bug.id))["allowed_actions"]


@pytest.mark.asyncio
async def test_recurrence_on_task_refused(factories, rig):
    task = await factories.issue(project_id=rig["project"].id, type="task")
    resp = await recur(rig["dev_client"], task.id)
    assert resp.status_code == 409
    assert resp.json()["code"] == "recurrence_bug_only"
    issue = await get(rig["dev_client"], task.id)
    assert "report_recurrence" not in issue["allowed_actions"]
    assert blocked(issue, "report_recurrence") is None  # hidden, not disabled


# ── AC-13 — concurrent recurrences both count ────────────────────────────────


@pytest.mark.asyncio
async def test_ac_13_concurrent_recurrences_both_counted(factories, rig):
    bug = await support_report(factories, rig)
    r1, r2 = await asyncio.gather(
        recur(rig["support_client"], bug.id, comment="Customer A"),
        recur(rig["other_support_client"], bug.id, comment="Customer B"),
    )
    assert r1.status_code == 201 and r2.status_code == 201
    assert sorted([r1.json()["recurrence_count"], r2.json()["recurrence_count"]]) == [2, 3]
    assert (await get(rig["admin"], bug.id))["recurrence_count"] == 3
    events = [e for e in await timeline(rig["admin"], bug.id) if e["event_type"] == "recurrence"]
    assert sorted(e["body"] for e in events) == ["Customer A", "Customer B"]


# ── Visibility (BR-30) ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_support_cannot_report_recurrence_on_non_support_bug(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, client=rig["qa_client"])
    resp = await recur(rig["support_client"], bug.id)
    assert resp.status_code == 404
    assert (await get(rig["admin"], bug.id))["recurrence_count"] == 1


@pytest.mark.asyncio
async def test_support_recurrence_makes_no_internal_bug_visible(factories, rig):
    """A subscription from a recurrence can only exist on a bug Support could already see."""
    bug = await support_report(factories, rig)
    assert (await recur(rig["other_support_client"], bug.id)).status_code == 201
    other = await factories.issue(project_id=rig["project"].id)
    assert (await rig["other_support_client"].get(f"/issues/{other.id}")).status_code == 404


# ── Support reports list (story 12) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_support_reports_rows_carry_recurrence_action(factories, rig):
    open_bug = await support_report(factories, rig)
    done_bug = await support_report(factories, rig)
    await rig["lead_client"].post(f"/issues/{done_bug.id}/triage", json={"outcome": "accept", "priority": "high"})
    await to_status(rig["admin"], done_bug.id, "done")

    rows = {r["id"]: r for r in (await rig["support_client"].get("/support/reports")).json()["items"]}
    assert rows[open_bug.id]["allowed_actions"] == ["report_recurrence"]
    assert rows[open_bug.id]["blocked_actions"] == []
    assert rows[done_bug.id]["allowed_actions"] == []
    assert rows[done_bug.id]["blocked_actions"] == [
        {"action": "report_recurrence", "code": "recurrence_on_done", "detail": FR_16},
    ]


# ── Issue list sort ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_issue_list_sorts_by_most_reported(factories, rig):
    once = await factories.issue(project_id=rig["project"].id)
    thrice = await factories.issue(project_id=rig["project"].id)
    twice = await factories.issue(project_id=rig["project"].id)
    for bug, times in ((thrice, 2), (twice, 1)):
        for _ in range(times):
            assert (await recur(rig["admin"], bug.id)).status_code == 201

    resp = await rig["admin"].get("/issues", params={"project_id": rig["project"].id, "sort": "reported"})
    assert resp.status_code == 200
    assert [i["id"] for i in resp.json()["items"]] == [thrice.id, twice.id, once.id]
