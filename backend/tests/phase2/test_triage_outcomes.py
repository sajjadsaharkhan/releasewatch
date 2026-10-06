"""Slice 06 — triage outcomes, merge, subscribers, and Support notifications.

docs/phase-2/06-triage-outcomes.md (FR-17–20, BR-16–21, BR-49/50,
AC-14–22, AC-49–54, §13). Observations go through HTTP responses, each
recipient's ``GET /inbox``, and the Telegram recorder.
"""

import asyncio

import pytest
import pytest_asyncio

TRIAGE_QUEUE = {"statuses": "new,needs_info", "sort": "oldest"}
BOARD = {"statuses": "todo,in_progress,in_review,done,blocked"}


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


async def support_report(factories, rig, **kw):
    return await factories.support_report(rig["support_client"], template=rig["template"], **kw)


async def inbox(client) -> list[dict]:
    return (await client.get("/inbox", params={"size": 100})).json()["items"]


async def inbox_types(client) -> list[str]:
    return [i["type"] for i in await inbox(client)]


async def triage(client, issue_id, **body):
    return await client.post(f"/issues/{issue_id}/triage", json=body)


async def timeline(client, issue_id) -> list[dict]:
    return (await client.get(f"/issues/{issue_id}/timeline", params={"size": 200})).json()["items"]


async def get(client, issue_id) -> dict:
    return (await client.get(f"/issues/{issue_id}")).json()


async def to_status(client, issue_id, to, **extra):
    resp = await client.post(f"/issues/{issue_id}/transition", json={"to": to, **extra})
    assert resp.status_code == 200, resp.text
    return resp.json()


def triaged_events(events) -> list[dict]:
    return [e["meta"] for e in events if e["event_type"] == "triaged"]


# ── Queue (FR-17, AC-14) ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_14_dev_filed_bug_enters_triage_not_board(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, client=rig["dev_client"])
    assert bug.status == "new"

    params = {**TRIAGE_QUEUE, "project_id": rig["project"].id}
    queue = (await rig["lead_client"].get("/issues", params=params)).json()["items"]
    assert [i["id"] for i in queue] == [bug.id]
    board = (await rig["lead_client"].get(
        "/issues", params={**BOARD, "project_id": rig["project"].id},
    )).json()["items"]
    assert bug.id not in [i["id"] for i in board]


@pytest.mark.asyncio
async def test_queue_is_oldest_first_and_shows_source_and_recurrence(factories, rig):
    first = await support_report(factories, rig, title="First")
    second = await factories.issue(project_id=rig["project"].id, client=rig["qa_client"])
    params = {**TRIAGE_QUEUE, "project_id": rig["project"].id}
    queue = (await rig["lead_client"].get("/issues", params=params)).json()["items"]
    assert [i["id"] for i in queue] == [first.id, second.id]
    assert queue[0]["source"] == "support" and queue[1]["source"] == "internal"
    assert all(i["recurrence_count"] == 1 for i in queue)
    assert queue[0]["reporter_user"]["id"] == rig["support"].id


# ── Accept (FR-18, BR-16, AC-15, AC-16) ──────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_15_non_lead_developer_can_accept(factories, rig, telegram):
    bug = await support_report(factories, rig)
    await telegram.link_telegram(rig["qa"])

    resp = await triage(
        rig["dev_client"], bug.id, outcome="accept", priority="high", assignee_id=rig["qa"].id,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "todo"
    assert body["priority"] == "high"
    assert body["assignee_id"] == rig["qa"].id
    assert body["release_id"] is None  # a support report accepted with no release: hotfix path

    # The assignee is notified (story 6).
    assert "assigned" in await inbox_types(rig["qa_client"])
    assert "assigned" in [t for t, _ in telegram.sent_to(rig["qa"])]

    # The decision is on the timeline with its inputs (story 23).
    assert triaged_events(await timeline(rig["admin"], bug.id)) == [{
        "outcome": "accept", "priority": "high",
        "assignee_id": rig["qa"].id, "release_id": None,
    }]


@pytest.mark.asyncio
async def test_ac_16_accept_requires_priority(factories, rig):
    bug = await support_report(factories, rig)
    resp = await triage(rig["dev_client"], bug.id, outcome="accept")
    assert resp.status_code == 422
    resp = await triage(rig["dev_client"], bug.id, outcome="accept", priority=None)
    assert resp.status_code == 422
    assert (await get(rig["admin"], bug.id))["status"] == "new"


@pytest.mark.asyncio
async def test_accept_without_assignee_is_allowed(factories, rig):
    bug = await support_report(factories, rig)
    resp = await triage(rig["lead_client"], bug.id, outcome="accept", priority="low")
    assert resp.status_code == 200
    assert resp.json()["assignee_id"] is None and resp.json()["status"] == "todo"


@pytest.mark.asyncio
async def test_accept_release_is_optional_and_null_clears_it(factories, rig):
    release = await factories.release(project_id=rig["project"].id)
    other = await factories.release(project_id=(await factories.project()).id)

    placed = await support_report(factories, rig)
    resp = await triage(rig["lead_client"], placed.id, outcome="accept", priority="medium", release_id=release.id)
    assert resp.status_code == 200 and resp.json()["release_id"] == release.id

    kept = await factories.issue(project_id=rig["project"].id, release_id=release.id)
    resp = await triage(rig["lead_client"], kept.id, outcome="accept", priority="medium")
    assert resp.json()["release_id"] == release.id  # omitted keeps the bug's release

    hotfix = await factories.issue(project_id=rig["project"].id, release_id=release.id)
    resp = await triage(rig["lead_client"], hotfix.id, outcome="accept", priority="medium", release_id=None)
    assert resp.json()["release_id"] is None  # explicit null is the hotfix path

    wrong = await support_report(factories, rig)
    resp = await triage(rig["lead_client"], wrong.id, outcome="accept", priority="medium", release_id=other.id)
    assert resp.status_code == 409 and resp.json()["code"] == "release_project_mismatch"


@pytest.mark.asyncio
async def test_accept_refuses_support_assignee(factories, rig):
    bug = await support_report(factories, rig)
    resp = await triage(
        rig["lead_client"], bug.id, outcome="accept", priority="low", assignee_id=rig["support"].id,
    )
    assert resp.status_code == 422 and resp.json()["code"] == "not_assignable"


@pytest.mark.asyncio
async def test_triage_only_from_new_or_needs_info(factories, rig):
    bug = await support_report(factories, rig)
    assert (await triage(rig["lead_client"], bug.id, outcome="accept", priority="low")).status_code == 200
    for body in (
        {"outcome": "accept", "priority": "low"},
        {"outcome": "needs_info", "comment": "More?"},
        {"outcome": "reject", "comment": "No."},
    ):
        resp = await triage(rig["lead_client"], bug.id, **body)
        assert resp.status_code == 409 and resp.json()["code"] == "not_in_triage", body


@pytest.mark.asyncio
async def test_support_cannot_triage(factories, rig):
    bug = await support_report(factories, rig)
    resp = await triage(rig["support_client"], bug.id, outcome="accept", priority="low")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_phase1_triage_endpoints_are_gone(factories, rig):
    bug = await support_report(factories, rig)
    for url, body in (
        (f"/issues/{bug.id}/needs-clarification", {"message": "x"}),
        (f"/issues/{bug.id}/duplicate", {"parent_id": bug.id}),
    ):
        assert (await rig["admin"].post(url, json=body)).status_code in (404, 405)


# ── Needs info (BR-18/19, AC-17–19) ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_17_needs_info_requires_comment(factories, rig):
    bug = await support_report(factories, rig)
    assert (await triage(rig["lead_client"], bug.id, outcome="needs_info")).status_code == 422
    assert (await triage(rig["lead_client"], bug.id, outcome="needs_info", comment="   ")).status_code == 422
    assert (await get(rig["admin"], bug.id))["status"] == "new"


@pytest.mark.asyncio
async def test_needs_info_posts_public_question_and_tells_support(factories, rig, telegram):
    bug = await support_report(factories, rig)
    await telegram.link_telegram(rig["support"])
    question = "Which app version is the customer on?"

    resp = await triage(rig["lead_client"], bug.id, outcome="needs_info", comment=question)
    assert resp.status_code == 200 and resp.json()["status"] == "needs_info"

    # The question is a public comment the reporter can read.
    events = await timeline(rig["support_client"], bug.id)
    asked = [e for e in events if e["event_type"] == "comment" and e["body"] == question]
    assert len(asked) == 1 and not asked[0]["is_internal"]
    assert asked[0]["meta"]["needs_info_question"] is True
    assert triaged_events(await timeline(rig["admin"], bug.id))[0]["outcome"] == "needs_info"

    items = await inbox(rig["support_client"])
    assert [i["type"] for i in items] == ["support_needs_info"]
    assert items[0]["meta"]["body_snippet"] == question
    sent = telegram.sent_to(rig["support"])
    assert [t for t, _ in sent] == ["support_needs_info"]
    assert question in sent[0][1]["excerpt"]


@pytest.mark.asyncio
async def test_ac_18_support_reply_returns_to_new_and_notifies_lead(factories, rig, telegram):
    bug = await support_report(factories, rig)
    await telegram.link_telegram(rig["lead"])
    await triage(rig["lead_client"], bug.id, outcome="needs_info", comment="Steps please?")

    resp = await rig["support_client"].post(
        f"/issues/{bug.id}/timeline", json={"body": "Tap Pay twice, then Back."},
    )
    assert resp.status_code == 201
    assert (await get(rig["admin"], bug.id))["status"] == "new"
    items = [i for i in await inbox(rig["lead_client"]) if i["type"] == "needs_info_replied"]
    assert len(items) == 1 and items[0]["meta"]["body_snippet"] == "Tap Pay twice, then Back."
    assert "needs_info_replied" in [t for t, _ in telegram.sent_to(rig["lead"])]


@pytest.mark.asyncio
async def test_any_support_user_reply_counts(factories, rig):
    bug = await support_report(factories, rig)
    await triage(rig["lead_client"], bug.id, outcome="needs_info", comment="Steps please?")
    await rig["other_support_client"].post(f"/issues/{bug.id}/timeline", json={"body": "Answering for them"})
    assert (await get(rig["admin"], bug.id))["status"] == "new"


@pytest.mark.asyncio
async def test_tech_reporter_reply_returns_to_new(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, client=rig["qa_client"])
    await triage(rig["lead_client"], bug.id, outcome="needs_info", comment="Which build?")
    await rig["qa_client"].post(f"/issues/{bug.id}/timeline", json={"body": "Build 412"})
    assert (await get(rig["admin"], bug.id))["status"] == "new"


@pytest.mark.asyncio
async def test_ac_19_developer_comment_keeps_needs_info(factories, rig):
    bug = await support_report(factories, rig)
    await triage(rig["lead_client"], bug.id, outcome="needs_info", comment="Steps please?")
    await rig["dev_client"].post(f"/issues/{bug.id}/timeline", json={"body": "I think it's the SDK"})
    assert (await get(rig["admin"], bug.id))["status"] == "needs_info"
    # A reporter's internal note doesn't count either — only a public reply does.
    qa_bug = await factories.issue(project_id=rig["project"].id, client=rig["qa_client"])
    await triage(rig["lead_client"], qa_bug.id, outcome="needs_info", comment="Which build?")
    await rig["qa_client"].post(
        f"/issues/{qa_bug.id}/timeline", json={"body": "note to self", "is_internal": True},
    )
    assert (await get(rig["admin"], qa_bug.id))["status"] == "needs_info"


@pytest.mark.asyncio
async def test_needs_info_again_asks_a_follow_up(factories, rig):
    bug = await support_report(factories, rig)
    await triage(rig["lead_client"], bug.id, outcome="needs_info", comment="First?")
    resp = await triage(rig["lead_client"], bug.id, outcome="needs_info", comment="And second?")
    assert resp.status_code == 200 and resp.json()["status"] == "needs_info"
    assert await inbox_types(rig["support_client"]) == ["support_needs_info", "support_needs_info"]


# ── Reject (FR-18) ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reject_cancels_with_reason_and_tells_support(factories, rig, telegram):
    bug = await support_report(factories, rig)
    await telegram.link_telegram(rig["support"])
    resp = await triage(
        rig["lead_client"], bug.id, outcome="reject", comment="Tried on three devices.",
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled" and resp.json()["cancel_reason"] is None

    events = await timeline(rig["support_client"], bug.id)
    assert "Tried on three devices." in [e["body"] for e in events]
    assert triaged_events(await timeline(rig["admin"], bug.id)) == [
        {"outcome": "reject"},
    ]
    items = await inbox(rig["support_client"])
    assert [i["type"] for i in items] == ["support_cancelled"]
    # No structured reason is stored: Support reads the triager's comment.
    assert items[0]["meta"]["reason_label"] == "Tried on three devices."
    sent = telegram.sent_to(rig["support"])
    assert [t for t, _ in sent] == ["support_cancelled"]
    assert sent[0][1]["cancel_reason"] == "Tried on three devices."


@pytest.mark.asyncio
async def test_reject_requires_a_comment(factories, rig):
    bug = await support_report(factories, rig)
    for body in ({}, {"comment": ""}, {"comment": "   "}):
        resp = await triage(rig["lead_client"], bug.id, outcome="reject", **body)
        assert resp.status_code == 422, body


# ── Duplicate / merge (FR-18, BR-20, BR-49/50, AC-20/21, AC-49–54) ───────────


@pytest.mark.asyncio
async def test_ac_20_duplicate_cancels_increments_and_subscribes(factories, rig, telegram):
    original = await factories.issue(project_id=rig["project"].id, client=rig["qa_client"])
    dup = await support_report(factories, rig, title="Checkout freezes", description="On Android 14")
    await telegram.link_telegram(rig["support"])

    resp = await triage(
        rig["lead_client"], dup.id, outcome="duplicate", duplicate_of_id=original.id,
        comment="Same crash as the QA report.",
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "duplicate"
    assert body["parent_issue_id"] == original.id
    assert (await get(rig["admin"], original.id))["recurrence_count"] == 2
    assert triaged_events(await timeline(rig["admin"], dup.id)) == [{
        "outcome": "duplicate", "duplicate_of_id": original.id,
        "duplicate_of_key": f"BUG-{original.issue_number}",
    }]
    # The duplicate's reporter learns it was merged — and into what…
    items = await inbox(rig["support_client"])
    assert [i["type"] for i in items] == ["support_cancelled"]
    assert items[0]["meta"]["merged_into_id"] == original.id
    assert items[0]["meta"]["merged_into_key"] == f"BUG-{original.issue_number}"
    sent = telegram.sent_to(rig["support"])
    assert [t for t, _ in sent] == ["support_merged"]
    assert sent[0][1]["merged_into_key"] == f"BUG-{original.issue_number}"

    # Subscribed, Support can open the internal original — public content only
    # (2026-09-24 decision: BR-30 widened to subscribed items; BR-31 still holds).
    await rig["admin"].post(
        f"/issues/{original.id}/timeline", json={"body": "Internal: SDK bug", "is_internal": True},
    )
    assert (await rig["support_client"].get(f"/issues/{original.id}")).status_code == 200
    seen = await timeline(rig["support_client"], original.id)
    assert any((e["meta"] or {}).get("merged_from_id") == dup.id for e in seen)
    assert not any(e["is_internal"] for e in seen)
    # Other internal bugs stay invisible.
    unrelated = await factories.issue(project_id=rig["project"].id)
    assert (await rig["support_client"].get(f"/issues/{unrelated.id}")).status_code == 404

    # …and now hears the original's future Support notices (BR-20, AC-20).
    await triage(rig["lead_client"], original.id, outcome="accept", priority="high")
    await to_status(rig["admin"], original.id, "done")
    items = await inbox(rig["support_client"])
    assert [i["type"] for i in items] == ["support_done", "support_cancelled"]
    assert items[0]["issueId"] == f"issue-{original.issue_number}"
    assert [t for t, _ in telegram.sent_to(rig["support"])] == ["support_merged", "support_done"]


@pytest.mark.asyncio
async def test_ac_21_duplicate_of_duplicate_blocked_with_suggestion(factories, rig):
    original = await factories.issue(project_id=rig["project"].id)
    first = await factories.issue(project_id=rig["project"].id)
    third = await factories.issue(project_id=rig["project"].id)
    await triage(rig["lead_client"], first.id, outcome="duplicate", duplicate_of_id=original.id)

    resp = await triage(rig["lead_client"], third.id, outcome="duplicate", duplicate_of_id=first.id)
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "duplicate_of_duplicate"
    assert body["suggested_id"] == original.id
    assert body["suggested_key"] == f"BUG-{original.issue_number}"
    assert (await get(rig["admin"], third.id))["status"] == "new"


@pytest.mark.asyncio
async def test_duplicate_refusals(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id)
    elsewhere = await factories.issue(project_id=(await factories.project()).id)

    cases = [
        (bug.id, "duplicate_of_self"),
        (elsewhere.id, "duplicate_cross_project"),
    ]
    for target, code in cases:
        resp = await triage(rig["lead_client"], bug.id, outcome="duplicate", duplicate_of_id=target)
        assert resp.status_code == 409 and resp.json()["code"] == code, (code, resp.text)
    resp = await triage(rig["lead_client"], bug.id, outcome="duplicate", duplicate_of_id=999_999)
    assert resp.status_code == 404
    assert (await get(rig["admin"], bug.id))["status"] == "new"


@pytest.mark.asyncio
async def test_ac_49_merge_into_open_copies_content_keeps_status(factories, rig):
    b = await factories.issue(project_id=rig["project"].id)
    earlier = await factories.issue(project_id=rig["project"].id)
    await triage(rig["lead_client"], earlier.id, outcome="duplicate", duplicate_of_id=b.id)
    await triage(rig["lead_client"], b.id, outcome="accept", priority="high")
    await to_status(rig["admin"], b.id, "in_progress")
    assert (await get(rig["admin"], b.id))["recurrence_count"] == 2

    a = await support_report(factories, rig, title="Pay button dead", description="Nothing happens on tap")
    resp = await triage(rig["lead_client"], a.id, outcome="duplicate", duplicate_of_id=b.id)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled" and resp.json()["cancel_reason"] == "duplicate"

    after = await get(rig["admin"], b.id)
    assert after["status"] == "in_progress"
    assert after["recurrence_count"] == 3
    merged = [
        e for e in await timeline(rig["admin"], b.id)
        if e["event_type"] == "comment" and (e["meta"] or {}).get("merged_from_id") == a.id
    ]
    assert len(merged) == 1
    comment = merged[0]
    assert not comment["is_internal"]
    assert comment["body"].startswith(f"Merged from [BUG-{a.issue_number}](/issue/bug-{a.issue_number})")
    assert "Pay button dead" in comment["body"] and "Nothing happens on tap" in comment["body"]


@pytest.mark.asyncio
async def test_ac_50_merge_into_done_stream_item_is_production_return(factories, rig, client_for):
    stream_id = await factories.stream_id(project_id=rig["project"].id)
    b = await factories.issue(project_id=rig["project"].id)
    await triage(
        rig["lead_client"], b.id, outcome="accept", priority="high",
        assignee_id=rig["developer"].id, release_id=stream_id,
    )
    await to_status(rig["admin"], b.id, "done")

    a = await factories.issue(project_id=rig["project"].id)
    resp = await triage(rig["lead_client"], a.id, outcome="duplicate", duplicate_of_id=b.id)
    assert resp.status_code == 200, resp.text

    after_b = await get(rig["admin"], b.id)
    assert after_b["status"] == "rejected"
    assert after_b["release_id"] == stream_id
    assert after_b["recurrence_count"] == 2
    assert after_b["reject_reason"] == "production"
    cycles = await factories.cycles(b.id)
    assert [c["start_reason"] for c in cycles] == ["planned", "production"]
    assert cycles[1]["start_merged_issue_id"] == a.id
    # The merge comment is the reason the work came back.
    merged = [
        e for e in await timeline(rig["admin"], b.id)
        if e["event_type"] == "comment" and (e["meta"] or {}).get("merged_from_id") == a.id
    ]
    assert cycles[1]["start_comment_id"] == merged[0]["id"]

    # The assignee hears it came back — not the Phase 1 regression notice.
    types = await inbox_types(rig["dev_client"])
    assert "item_returned" in types and "regression" not in types


@pytest.mark.asyncio
async def test_ac_51_merge_into_done_in_release_in_qa_is_release_qa(factories, rig):
    release = await factories.release(project_id=rig["project"].id)
    await factories.set_release_status(release.id, "qa")
    b = await factories.issue(project_id=rig["project"].id, release_id=release.id)
    await triage(rig["lead_client"], b.id, outcome="accept", priority="high")
    await to_status(rig["admin"], b.id, "done")

    a = await factories.issue(project_id=rig["project"].id)
    assert (await triage(rig["lead_client"], a.id, outcome="duplicate", duplicate_of_id=b.id)).status_code == 200
    after = await get(rig["admin"], b.id)
    assert after["status"] == "rejected" and after["release_id"] == release.id
    cycles = await factories.cycles(b.id)
    assert [(c["start_reason"], c["release_id"]) for c in cycles] == [
        ("planned", release.id), ("release_qa", release.id),
    ]
    assert cycles[1]["start_merged_issue_id"] == a.id


@pytest.mark.asyncio
async def test_merge_into_done_item_of_released_release_moves_to_stream(factories, rig):
    stream_id = await factories.stream_id(project_id=rig["project"].id)
    release = await factories.release(project_id=rig["project"].id)
    b = await factories.issue(project_id=rig["project"].id, release_id=release.id)
    await triage(rig["lead_client"], b.id, outcome="accept", priority="high")
    await to_status(rig["admin"], b.id, "done")
    await factories.set_release_status(release.id, "released")

    a = await factories.issue(project_id=rig["project"].id)
    assert (await triage(rig["lead_client"], a.id, outcome="duplicate", duplicate_of_id=b.id)).status_code == 200
    after = await get(rig["admin"], b.id)
    assert after["status"] == "rejected" and after["release_id"] == stream_id
    cycles = await factories.cycles(b.id)
    assert [(c["start_reason"], c["release_id"]) for c in cycles] == [
        ("planned", release.id), ("production", stream_id),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["todo", "in_progress", "in_review", "blocked"])
async def test_ac_52_merge_into_open_item_starts_no_cycle(factories, rig, status):
    release = await factories.release(project_id=rig["project"].id)
    b = await factories.issue(project_id=rig["project"].id, release_id=release.id)
    await triage(rig["lead_client"], b.id, outcome="accept", priority="high")
    if status != "todo":
        await to_status(rig["admin"], b.id, status)
    a = await factories.issue(project_id=rig["project"].id)
    assert (await triage(rig["lead_client"], a.id, outcome="duplicate", duplicate_of_id=b.id)).status_code == 200
    after = await get(rig["admin"], b.id)
    assert after["status"] == status and after["reject_reason"] is None
    assert after["cycle_count"] == 1
    assert after["recurrence_count"] == 2


@pytest.mark.asyncio
async def test_ac_53_merge_into_cancelled_stays_cancelled_notifies_lead(factories, rig, telegram):
    b = await factories.issue(project_id=rig["project"].id)
    await triage(rig["lead_client"], b.id, outcome="reject", comment="Expected behavior.")
    await telegram.link_telegram(rig["lead"])

    a = await factories.issue(project_id=rig["project"].id, client=rig["qa_client"])
    assert (await triage(rig["admin"], a.id, outcome="duplicate", duplicate_of_id=b.id)).status_code == 200
    after = await get(rig["admin"], b.id)
    assert after["status"] == "cancelled"
    assert after["cancel_reason"] is None
    assert after["recurrence_count"] == 2
    assert "recurrence_on_cancelled" in await inbox_types(rig["lead_client"])
    assert "recurrence_on_cancelled" in [t for t, _ in telegram.sent_to(rig["lead"])]


@pytest.mark.asyncio
async def test_ac_54_merged_support_reporter_gets_done_after_return(factories, rig, telegram):
    stream_id = await factories.stream_id(project_id=rig["project"].id)
    b = await factories.issue(project_id=rig["project"].id)
    await triage(rig["lead_client"], b.id, outcome="accept", priority="high", release_id=stream_id)
    await to_status(rig["admin"], b.id, "done")

    a = await support_report(factories, rig)
    await telegram.link_telegram(rig["support"])
    await triage(rig["lead_client"], a.id, outcome="duplicate", duplicate_of_id=b.id)
    # The return itself sends Support nothing (§13) — only A's cancellation.
    assert await inbox_types(rig["support_client"]) == ["support_cancelled"]
    assert (await get(rig["admin"], b.id))["status"] == "rejected"

    await to_status(rig["admin"], b.id, "in_review")
    await to_status(rig["admin"], b.id, "done")
    assert await inbox_types(rig["support_client"]) == ["support_done", "support_cancelled"]
    assert [t for t, _ in telegram.sent_to(rig["support"])] == ["support_merged", "support_done"]


@pytest.mark.asyncio
async def test_ac_77_merge_into_done_task_in_stream(factories, rig, client_for):
    stream_id = await factories.stream_id(project_id=rig["project"].id)
    task = await factories.issue(project_id=rig["project"].id, type="task", release_id=stream_id)
    await to_status(rig["admin"], task.id, "done")

    a = await support_report(factories, rig)
    resp = await triage(rig["lead_client"], a.id, outcome="duplicate", duplicate_of_id=task.id)
    assert resp.status_code == 200, resp.text

    after = await get(rig["admin"], task.id)
    assert after["status"] == "rejected" and after["release_id"] == stream_id
    assert after["reject_reason"] == "production"
    # A task has no recurrence count (BR-22 is bug-only).
    assert after["recurrence_count"] == 1
    # A's reporter is subscribed to T — Support can now see it.
    support_view = await rig["support_client"].get(f"/issues/{task.id}")
    assert support_view.status_code == 200


@pytest.mark.asyncio
async def test_concurrent_duplicates_both_count(factories, rig, client_for):
    original = await factories.issue(project_id=rig["project"].id)
    first = await factories.issue(project_id=rig["project"].id)
    second = await factories.issue(project_id=rig["project"].id)
    other_client = await client_for(rig["developer"])

    r1, r2 = await asyncio.gather(
        triage(rig["lead_client"], first.id, outcome="duplicate", duplicate_of_id=original.id),
        triage(other_client, second.id, outcome="duplicate", duplicate_of_id=original.id),
    )
    assert r1.status_code == 200 and r2.status_code == 200
    assert (await get(rig["admin"], original.id))["recurrence_count"] == 3


# ── Move project (FR-20, BR-05, AC-22) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_22_move_project_notifies_new_lead(factories, rig, telegram, client_for):
    new_lead = await factories.user(role="qa")
    new_lead_client = await client_for(new_lead)
    target = await factories.project(triage_lead_id=new_lead.id)
    bug = await support_report(factories, rig)
    await telegram.link_telegram(new_lead)

    resp = await rig["lead_client"].post(f"/issues/{bug.id}/move", json={"project_id": target.id})
    assert resp.status_code == 200, resp.text
    assert resp.json()["project_id"] == target.id

    queue = (await rig["admin"].get("/issues", params={**TRIAGE_QUEUE, "project_id": target.id})).json()
    assert [i["id"] for i in queue["items"]] == [bug.id]
    events = await timeline(rig["admin"], bug.id)
    assert any(e["event_type"] == "project_changed" and e["meta"]["to_name"] == target.name for e in events)
    assert "moved_into_project" in await inbox_types(new_lead_client)
    assert "moved_into_project" in [t for t, _ in telegram.sent_to(new_lead)]
    # The old project's lead isn't told about it.
    assert "moved_into_project" not in await inbox_types(rig["lead_client"])


@pytest.mark.asyncio
async def test_move_refusals(factories, rig):
    target = await factories.project()
    fresh = await support_report(factories, rig)

    async def move(issue_id, project_id):
        return await rig["lead_client"].post(f"/issues/{issue_id}/move", json={"project_id": project_id})

    resp = await move(fresh.id, rig["project"].id)
    assert resp.status_code == 409 and resp.json()["code"] == "same_project"
    assert (await move(fresh.id, 999_999)).status_code == 404
    assert (await rig["support_client"].post(
        f"/issues/{fresh.id}/move", json={"project_id": target.id},
    )).status_code == 403


# ── Support audience (§13, BR-31) ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_support_subscriber_gets_only_the_three_events_and_mentions(factories, rig, telegram):
    """filed → needs info → replied → accepted → in progress → in review → done.

    Support hears the three Support notices, plus a public @mention (the
    2026-09-24 decision) — never plain comments or status changes.
    """
    await telegram.link_telegram(rig["support"])
    bug = await support_report(factories, rig)
    sid = rig["support"].id

    await triage(rig["lead_client"], bug.id, outcome="needs_info", comment="Which account?")
    await rig["support_client"].post(f"/issues/{bug.id}/timeline", json={"body": "acct 42"})
    await triage(rig["lead_client"], bug.id, outcome="accept", priority="high", assignee_id=rig["developer"].id)
    # A plain comment never reaches Support; a public mention does.
    await rig["dev_client"].post(f"/issues/{bug.id}/timeline", json={"body": "On it"})
    await rig["dev_client"].post(
        f"/issues/{bug.id}/timeline",
        json={"body": "Can you confirm with the customer?", "mentioned_user_ids": [sid]},
    )
    # …but never an internal note, mention or not (BR-31).
    await rig["dev_client"].post(
        f"/issues/{bug.id}/timeline",
        json={"body": "internal", "is_internal": True, "mentioned_user_ids": [sid]},
    )
    await rig["dev_client"].post(f"/issues/{bug.id}/transition", json={"to": "in_progress"})
    await rig["dev_client"].post(f"/issues/{bug.id}/fix", json={"mr_url": None})
    await rig["qa_client"].post(f"/issues/{bug.id}/verify", json={"outcome": "pass"})
    assert (await get(rig["admin"], bug.id))["status"] == "done"

    assert await inbox_types(rig["support_client"]) == ["support_done", "mention", "support_needs_info"]
    assert [t for t, _ in telegram.sent_to(rig["support"])] == ["support_needs_info", "mention", "support_done"]

    # The third event, on a second report.
    rejected = await support_report(factories, rig)
    await triage(rig["lead_client"], rejected.id, outcome="reject", comment="User error.")
    assert set(await inbox_types(rig["support_client"])) == {
        "support_needs_info", "support_cancelled", "support_done", "mention",
    }


@pytest.mark.asyncio
async def test_tech_reporter_keeps_phase1_notifications(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, client=rig["qa_client"])
    await triage(rig["lead_client"], bug.id, outcome="needs_info", comment="Which build?")
    await rig["dev_client"].post(f"/issues/{bug.id}/timeline", json={"body": "Looking"})
    await rig["qa_client"].post(f"/issues/{bug.id}/timeline", json={"body": "Build 412"})
    await triage(rig["lead_client"], bug.id, outcome="accept", priority="high")
    await to_status(rig["lead_client"], bug.id, "done")

    types = await inbox_types(rig["qa_client"])
    assert "needs_clarification" in types
    assert "comment" in types
    assert types.count("status_changed") >= 3  # needs_info, todo, done
    assert not any(t.startswith("support_") for t in types)  # QA isn't Support


@pytest.mark.asyncio
async def test_matrix_has_subscriber_column_and_support_rows(factories):
    matrix = (await factories.admin_client.get("/settings/notifications")).json()
    assert all("subscriber" in row for row in matrix.values())
    for event in ("support_needs_info", "support_cancelled", "support_done"):
        assert matrix[event]["subscriber"] is True
        assert not any(v for k, v in matrix[event].items() if k != "subscriber")
    for event in ("needs_info_replied", "moved_into_project", "recurrence_on_cancelled"):
        assert matrix[event]["triage"] is True

    # A matrix saved without the new key still carries it.
    saved = (await factories.admin_client.put(
        "/settings/notifications", json={"comment": {"reporter": False, "assignee": True}},
    )).json()
    assert saved["comment"] == {
        "reporter": False, "assignee": True, "triage": False, "cto": False, "subscriber": False,
    }


@pytest.mark.asyncio
async def test_support_done_off_in_matrix_sends_no_telegram(factories, rig, telegram):
    await factories.admin_client.put(
        "/settings/notifications", json={"support_done": {"subscriber": False}},
    )
    await telegram.link_telegram(rig["support"])
    bug = await support_report(factories, rig)
    await triage(rig["lead_client"], bug.id, outcome="accept", priority="low")
    await to_status(rig["admin"], bug.id, "done")
    assert await inbox_types(rig["support_client"]) == ["support_done"]  # inbox still gets it
    assert telegram.sent_to(rig["support"]) == []


# ── Mentions and the Support reports list (2026-09-24 follow-up) ─────────────


@pytest.mark.asyncio
async def test_support_mentioned_on_a_teammates_report_is_notified(factories, rig):
    """Support works as a team: any Support user can see — and be pinged on —
    any support report."""
    bug = await support_report(factories, rig)  # filed by rig["support"]
    await rig["dev_client"].post(
        f"/issues/{bug.id}/timeline",
        json={"body": "Can you check?", "mentioned_user_ids": [rig["other_support"].id]},
    )
    items = await inbox(rig["other_support_client"])
    assert [i["type"] for i in items] == ["mention"]
    assert items[0]["issueId"] == f"issue-{bug.issue_number}"


@pytest.mark.asyncio
async def test_merge_comment_credits_reporter(factories, rig):
    original = await factories.issue(project_id=rig["project"].id)

    # A tech reporter is mentioned and notified — that's how they find out
    # where their report went.
    qa_dup = await factories.issue(project_id=rig["project"].id, client=rig["qa_client"])
    await triage(rig["lead_client"], qa_dup.id, outcome="duplicate", duplicate_of_id=original.id)
    # A Support reporter is credited too, but gets only the "merged" notice.
    support_dup = await support_report(factories, rig)
    await triage(rig["lead_client"], support_dup.id, outcome="duplicate", duplicate_of_id=original.id)

    merged = {
        (e["meta"] or {}).get("merged_from_id"): e
        for e in await timeline(rig["admin"], original.id) if e["event_type"] == "comment"
    }
    qa_comment, support_comment = merged[qa_dup.id], merged[support_dup.id]
    # The merged bug is a link; the credit is plain text, not a rendered @mention.
    assert qa_comment["body"].startswith(f"Merged from [BUG-{qa_dup.issue_number}](/issue/bug-{qa_dup.issue_number})")
    assert qa_comment["body"].endswith(f"Reported by {rig['qa'].username}")
    assert "@" not in qa_comment["body"]
    assert qa_comment["mentioned_user_ids"] == [rig["qa"].id]
    assert support_comment["body"].endswith(f"Reported by {rig['support'].username}")
    assert support_comment["mentioned_user_ids"] == [rig["support"].id]

    qa_mentions = [i for i in await inbox(rig["qa_client"]) if i["type"] == "mention"]
    assert [i["issueId"] for i in qa_mentions] == [f"issue-{original.issue_number}"]
    assert await inbox_types(rig["support_client"]) == ["support_cancelled"]


@pytest.mark.asyncio
async def test_merge_comment_carries_the_triagers_note(factories, rig):
    """The comment typed in the merge confirmation lands in the comment added to
    the original — between where it came from and the quoted report — and is
    still posted on the merged bug itself."""
    original = await factories.issue(project_id=rig["project"].id)
    dup = await factories.issue(project_id=rig["project"].id, title="Same crash on checkout")
    resp = await triage(
        rig["lead_client"], dup.id, outcome="duplicate", duplicate_of_id=original.id,
        comment="Same stack trace as the original; the reporter is on iOS 17.",
    )
    assert resp.status_code == 200

    merge = next(
        e for e in await timeline(rig["admin"], original.id)
        if e["event_type"] == "comment" and (e["meta"] or {}).get("merged_from_id") == dup.id
    )
    head, _, rest = merge["body"].partition("\n\n")
    assert head.startswith("Merged from [BUG-")
    assert rest.startswith("Same stack trace as the original; the reporter is on iOS 17.\n\n> **Same crash on checkout**")
    assert any(
        e["body"] == "Same stack trace as the original; the reporter is on iOS 17."
        for e in await timeline(rig["admin"], dup.id) if e["event_type"] == "comment"
    )

    # Without a note the comment is unchanged: the source line, then the quote.
    plain = await factories.issue(project_id=rig["project"].id, title="Another checkout crash")
    await triage(rig["lead_client"], plain.id, outcome="duplicate", duplicate_of_id=original.id)
    bare = next(
        e for e in await timeline(rig["admin"], original.id)
        if e["event_type"] == "comment" and (e["meta"] or {}).get("merged_from_id") == plain.id
    )
    assert bare["body"].split("\n\n")[1].startswith("> **Another checkout crash**")


@pytest.mark.asyncio
async def test_support_reports_list_shows_reporter_and_filters_to_me(factories, rig):
    mine = await support_report(factories, rig, title="Mine")
    theirs = await factories.support_report(
        rig["other_support_client"], template=rig["template"], title="Theirs",
    )

    everyone = (await rig["support_client"].get("/support/reports")).json()["items"]
    assert {r["id"] for r in everyone} == {mine.id, theirs.id}  # the whole team's reports
    by_id = {r["id"]: r for r in everyone}
    assert by_id[theirs.id]["reporter_user"]["id"] == rig["other_support"].id

    only_me = (await rig["support_client"].get(
        "/support/reports", params={"reporter_id": rig["support"].id},
    )).json()
    assert [r["id"] for r in only_me["items"]] == [mine.id] and only_me["total"] == 1


# ── Migration a7c3d9e1f2b4: drop the structured reason from triage rejections ─


async def test_reject_reason_migration_clears_only_triage_rejects_and_reverses(factories, rig, db_session):
    """Real rows through the migration's own SQL: a bug cancelled by a triage
    Reject loses its stored reason, one cancelled any other way keeps it, and
    the downgrade puts everything back."""
    import importlib.util
    import pathlib

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import text

    path = next((pathlib.Path(__file__).parents[2] / "alembic" / "versions").glob("a7c3d9e1f2b4_*.py"))
    spec = importlib.util.spec_from_file_location("reject_reason_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def run(fn) -> None:
        def _go(session):
            with Operations.context(MigrationContext.configure(session.connection())):
                fn()
        return db_session.run_sync(_go)

    async def reason_of(issue_id: int):
        return (await db_session.execute(
            text("SELECT cancel_reason FROM issues WHERE id = :i"), {"i": issue_id},
        )).scalar_one()

    # The test database is built at head, so the backup table already exists:
    # step back to the state before the migration first.
    await run(migration.downgrade)

    # Rejected through triage — then given the reason the old Reject stored.
    rejected = await factories.issue(project_id=rig["project"].id)
    assert (await triage(rig["lead_client"], rejected.id, outcome="reject", comment="Not a bug.")).status_code == 200
    await db_session.execute(text("UPDATE issues SET cancel_reason = 'user_error' WHERE id = :i"), {"i": rejected.id})

    # Accepted, then cancelled by hand with the same reason: not a triage reject.
    manual = await factories.issue(project_id=rig["project"].id)
    await triage(rig["lead_client"], manual.id, outcome="accept", priority="low")
    await to_status(rig["lead_client"], manual.id, "cancelled", cancel_reason="user_error")

    # A different reason on a triage reject is untouched too (wont_fix is not one of the three).
    other = await factories.issue(project_id=rig["project"].id)
    await triage(rig["lead_client"], other.id, outcome="reject", comment="No.")
    await db_session.execute(text("UPDATE issues SET cancel_reason = 'wont_fix' WHERE id = :i"), {"i": other.id})
    await db_session.commit()

    await run(migration.upgrade)
    assert await reason_of(rejected.id) is None
    assert await reason_of(manual.id) == "user_error"
    assert await reason_of(other.id) == "wont_fix"
    backed_up = dict((await db_session.execute(
        text("SELECT issue_id, cancel_reason FROM triage_reject_reason_backup"),
    )).all())
    assert backed_up == {rejected.id: "user_error"}

    await run(migration.downgrade)
    assert await reason_of(rejected.id) == "user_error"
    assert await reason_of(manual.id) == "user_error"
    gone = (await db_session.execute(text("SELECT to_regclass('triage_reject_reason_backup')"))).scalar_one()
    assert gone is None

    # Leave the database at head, as every other test expects it.
    await run(migration.upgrade)
    await db_session.commit()
