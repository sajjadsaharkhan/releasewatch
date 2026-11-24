"""Slice 21 — Support channel (per-project Telegram topic).

docs/phase-2/21-support-channel.md, PRD v3.1 §8.11, FR-70/71, BR-31, BR-72, §13,
AC-94–98. Telegram is recorded (``telegram.channel``), never sent; time is the
``clock`` fixture's. The outbox is drained by calling the task body the way the
beat does (``send_due_posts(now)``). Observations: the recorder, and the
settings endpoint's counters.
"""

import pytest
import pytest_asyncio
from sqlalchemy import update

from app.db.models.telegram_integration import TelegramIntegration
from app.tasks.support_channel import send_due_posts

CHAT_ID = -1001234567890
THREAD_ID = 42


@pytest_asyncio.fixture
async def rig(factories, client_for, clock):
    lead = await factories.user(role="developer")
    project = await factories.project(triage_lead_id=lead.id)
    release = await factories.release(project_id=project.id)
    stream_id = await factories.stream_id(project_id=project.id)
    dev = await factories.user(role="developer")
    qa = await factories.user(role="qa")
    cto = await factories.user(role="cto")
    support = await factories.user(role="support")
    template = await factories.support_template(project_id=project.id)
    return {
        "admin": factories.admin_client,
        "project": project, "release": release, "stream_id": stream_id,
        "lead": lead, "lead_client": await client_for(lead),
        "dev": dev, "dev_client": await client_for(dev),
        "qa": qa, "qa_client": await client_for(qa),
        "cto": cto, "cto_client": await client_for(cto),
        "support": support, "support_client": await client_for(support),
        "template": template,
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _enable(rig, *, chat_id=CHAT_ID, thread_id=THREAD_ID):
    """Save, test, enable — the only way an operator can turn the channel on."""
    c, pid = rig["cto_client"], rig["project"].id
    resp = await c.put(f"/projects/{pid}/support-channel",
                       json={"chat_id": chat_id, "thread_id": thread_id, "enabled": False})
    assert resp.status_code == 200, resp.text
    resp = await c.post(f"/projects/{pid}/support-channel/test")
    assert resp.status_code == 200 and resp.json()["ok"], resp.text
    resp = await c.put(f"/projects/{pid}/support-channel",
                       json={"chat_id": chat_id, "thread_id": thread_id, "enabled": True})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _drain(telegram, clock, *, advance: int = 0):
    """Advance the clock, run the sender once, and return the channel texts sent so far."""
    clock.advance(seconds=advance)
    await send_due_posts(clock())
    return [text for _, _, text in telegram.channel[1:]]  # [0] is the settings test message


async def _move(client, issue_id, *steps, expect=200):
    resp = None
    for to in steps:
        resp = await client.post(f"/issues/{issue_id}/transition", json={"to": to})
        assert resp.status_code == expect, resp.text
    return resp.json()


async def _report(factories, rig, **kw):
    return await factories.support_report(rig["support_client"], template=rig["template"], **kw)


async def _accept(rig, bug, *, container="stream"):
    release_id = rig["stream_id"] if container == "stream" else rig["release"].id
    resp = await rig["lead_client"].post(f"/issues/{bug.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": release_id,
        "assignee_id": rig["dev"].id,
    })
    assert resp.status_code == 200, resp.text


async def _bug(factories, rig, *, container="stream"):
    bug = await _report(factories, rig)
    await _accept(rig, bug, container=container)
    return bug


async def _settled(factories, rig, telegram, clock, **kw):
    """A support bug accepted into the stream, with the setup posts already sent."""
    bug = await _bug(factories, rig, **kw)
    await _drain(telegram, clock, advance=120)
    telegram.channel[1:] = []
    return bug


# ── Settings (FR-70) ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_cto_saves_tests_and_enables_the_channel(rig, telegram):
    state = await _enable(rig)
    assert state["chat_id"] == CHAT_ID and state["thread_id"] == THREAD_ID
    assert state["enabled"] is True and state["tested"] is True
    chat, thread, text = telegram.channel[0]
    assert (chat, thread) == (CHAT_ID, THREAD_ID)
    assert rig["project"].name in text


@pytest.mark.asyncio
async def test_enabling_without_a_passing_test_is_refused(rig):
    c, pid = rig["cto_client"], rig["project"].id
    resp = await c.put(f"/projects/{pid}/support-channel",
                       json={"chat_id": CHAT_ID, "thread_id": None, "enabled": True})
    assert resp.status_code == 409 and resp.json()["code"] == "support_channel_untested"
    state = (await c.get(f"/projects/{pid}/support-channel")).json()
    assert state["enabled"] is False


@pytest.mark.asyncio
async def test_changing_the_chat_or_topic_clears_the_test(rig):
    await _enable(rig)
    c, pid = rig["cto_client"], rig["project"].id
    resp = await c.put(f"/projects/{pid}/support-channel",
                       json={"chat_id": CHAT_ID, "thread_id": THREAD_ID + 1, "enabled": True})
    assert resp.status_code == 409 and resp.json()["code"] == "support_channel_untested"
    resp = await c.put(f"/projects/{pid}/support-channel",
                       json={"chat_id": CHAT_ID - 1, "thread_id": THREAD_ID, "enabled": False})
    assert resp.status_code == 200
    assert resp.json()["tested"] is False and resp.json()["enabled"] is False
    # Saving the same chat and topic again keeps a passing test.
    await c.post(f"/projects/{pid}/support-channel/test")
    resp = await c.put(f"/projects/{pid}/support-channel",
                       json={"chat_id": CHAT_ID - 1, "thread_id": THREAD_ID, "enabled": True})
    assert resp.status_code == 200 and resp.json()["tested"] is True


@pytest.mark.asyncio
async def test_a_failed_test_returns_telegrams_reason_and_does_not_stamp(rig, telegram):
    c, pid = rig["cto_client"], rig["project"].id
    await c.put(f"/projects/{pid}/support-channel",
                json={"chat_id": CHAT_ID, "thread_id": None, "enabled": False})
    telegram.channel_error = "chat not found"
    resp = await c.post(f"/projects/{pid}/support-channel/test")
    assert resp.status_code == 200
    assert resp.json()["ok"] is False and "chat not found" in resp.json()["error"]
    assert (await c.get(f"/projects/{pid}/support-channel")).json()["tested"] is False


@pytest.mark.asyncio
async def test_only_cto_and_admin_manage_the_channel(rig):
    pid = rig["project"].id
    for key in ("dev_client", "qa_client", "support_client", "lead_client"):
        c = rig[key]
        assert (await c.get(f"/projects/{pid}/support-channel")).status_code == 403
        resp = await c.put(f"/projects/{pid}/support-channel",
                           json={"chat_id": CHAT_ID, "enabled": False})
        assert resp.status_code == 403
        assert (await c.post(f"/projects/{pid}/support-channel/test")).status_code == 403
    assert (await rig["admin"].get(f"/projects/{pid}/support-channel")).status_code == 200


# ── AC-94 — a new report ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_94_a_new_report_posts_to_the_configured_chat_and_topic(
    factories, rig, telegram, clock, db_session,
):
    await _enable(rig)
    await telegram.link_telegram(rig["support"])
    await db_session.execute(
        update(TelegramIntegration)
        .where(TelegramIntegration.user_id == rig["support"].id)
        .values(telegram_username="sara_support")
    )
    await db_session.commit()

    bug = await _report(factories, rig, title="Login fails on iOS 17 <b>")
    await _drain(telegram, clock)  # a new report is due at once
    assert len(telegram.channel) == 2
    chat, thread, text = telegram.channel[1]
    assert (chat, thread) == (CHAT_ID, THREAD_ID)
    assert rig["project"].name in text
    assert f"BUG-{bug.issue_number}" in text
    assert "Login fails on iOS 17 &lt;b&gt;" in text  # HTML-escaped
    assert "@sara_support" in text
    assert f"/issue/bug-{bug.issue_number}" in text


@pytest.mark.asyncio
async def test_a_reporter_without_telegram_is_named(factories, rig, telegram, clock):
    await _enable(rig)
    await _report(factories, rig)
    texts = await _drain(telegram, clock)
    assert rig["support"].name in texts[0]


# ── AC-95 — one post per item per minute ──────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_95_changes_within_60_seconds_are_one_post(factories, rig, telegram, clock):
    await _enable(rig)
    bug = await _settled(factories, rig, telegram, clock)
    await _move(rig["admin"], bug.id, "in_progress", "to_review")
    await _drain(telegram, clock, advance=61)
    telegram.channel[1:] = []

    await _move(rig["qa_client"], bug.id, "in_review")
    clock.advance(seconds=20)
    await _move(rig["qa_client"], bug.id, "verified")
    assert await _drain(telegram, clock) == []  # still inside the window
    texts = await _drain(telegram, clock, advance=41)
    assert len(texts) == 1
    assert "To review" in texts[0] and "Verified" in texts[0]
    assert "In review" not in texts[0]
    assert await _drain(telegram, clock, advance=300) == texts  # posted once, never again


@pytest.mark.asyncio
async def test_ac_95_changes_two_minutes_apart_are_two_posts(factories, rig, telegram, clock):
    await _enable(rig)
    bug = await _settled(factories, rig, telegram, clock)
    await _move(rig["admin"], bug.id, "in_progress", "to_review")
    await _drain(telegram, clock, advance=61)
    telegram.channel[1:] = []

    await _move(rig["qa_client"], bug.id, "in_review")
    clock.advance(seconds=120)
    await _move(rig["qa_client"], bug.id, "verified")
    texts = await _drain(telegram, clock, advance=61)
    assert len(texts) == 2
    assert "To review → In review" in texts[0] and "In review → Verified" in texts[1]


@pytest.mark.asyncio
async def test_a_move_there_and_back_within_60_seconds_posts_nothing(
    factories, rig, telegram, clock,
):
    await _enable(rig)
    bug = await _settled(factories, rig, telegram, clock)
    await _move(rig["admin"], bug.id, "in_progress")
    await _drain(telegram, clock, advance=61)
    telegram.channel[1:] = []
    await _move(rig["admin"], bug.id, "blocked")
    await _move(rig["admin"], bug.id, "in_progress")
    assert await _drain(telegram, clock, advance=120) == []


# ── AC-81 — On production and ship are one post per project ──────────────────


@pytest.mark.asyncio
async def test_ac_81_on_production_for_three_items_is_one_batch_post(
    factories, rig, telegram, clock,
):
    await _enable(rig)
    bugs = [await _bug(factories, rig) for _ in range(3)]
    for bug in bugs:
        await _move(rig["admin"], bug.id, "in_progress", "in_review", "verified")
    await _drain(telegram, clock, advance=120)
    telegram.channel[1:] = []

    resp = await rig["dev_client"].post(
        "/issues/bulk-production", json={"issue_ids": [b.id for b in bugs]},
    )
    assert resp.status_code == 200, resp.text
    texts = await _drain(telegram, clock, advance=6)
    assert len(texts) == 1
    assert "On production · 3 items" in texts[0]
    for bug in bugs:
        assert f"BUG-{bug.issue_number}" in texts[0]


@pytest.mark.asyncio
async def test_ac_81_a_ship_with_four_verified_items_is_one_post(
    factories, rig, telegram, clock,
):
    await _enable(rig)
    bugs = [await _bug(factories, rig, container="release") for _ in range(4)]
    for bug in bugs:
        await _move(rig["admin"], bug.id, "in_progress", "in_review", "verified")
    await _drain(telegram, clock, advance=120)
    telegram.channel[1:] = []

    for to in ("development", "qa"):
        resp = await rig["admin"].post(f"/releases/{rig['release'].id}/status", json={"to": to})
        assert resp.status_code == 200, resp.text
    resp = await rig["admin"].post(f"/releases/{rig['release'].id}/ship", json={"confirm": True})
    assert resp.status_code == 200, resp.text
    texts = await _drain(telegram, clock, advance=6)
    assert len(texts) == 1
    assert f"Released {rig['release'].version}" in texts[0] and "4 items" in texts[0]
    for bug in bugs:
        assert f"BUG-{bug.issue_number}" in texts[0]


@pytest.mark.asyncio
async def test_a_ship_counts_only_what_reached_production(factories, rig, telegram, clock):
    await _enable(rig)
    done = [await _bug(factories, rig, container="release") for _ in range(2)]
    unfinished = await _bug(factories, rig, container="release")
    for bug in done:
        await _move(rig["admin"], bug.id, "in_progress", "in_review", "verified")
    await _move(rig["admin"], unfinished.id, "in_progress", "in_review")
    await _drain(telegram, clock, advance=120)
    telegram.channel[1:] = []

    for to in ("development", "qa"):
        resp = await rig["admin"].post(f"/releases/{rig['release'].id}/status", json={"to": to})
        assert resp.status_code == 200, resp.text
    resp = await rig["admin"].post(f"/releases/{rig['release'].id}/ship", json={"confirm": True})
    assert resp.status_code == 200, resp.text
    texts = await _drain(telegram, clock, advance=6)
    assert len(texts) == 1
    assert "· 2 items" in texts[0] and "Back to the backlog · 1" in texts[0]
    head, _, tail = texts[0].partition("Back to the backlog")
    assert f"BUG-{unfinished.issue_number}" in tail and f"BUG-{unfinished.issue_number}" not in head
    for bug in done:
        assert f"BUG-{bug.issue_number}" in head


@pytest.mark.asyncio
async def test_a_to_review_move_carries_no_reason_line(factories, rig, telegram, clock):
    await _enable(rig)
    bug = await _settled(factories, rig, telegram, clock)
    await _move(rig["admin"], bug.id, "in_progress")
    resp = await rig["dev_client"].post(
        f"/issues/{bug.id}/transition", json={"to": "to_review", "comment": "https://git/mr/1"},
    )
    assert resp.status_code == 200, resp.text
    texts = await _drain(telegram, clock, advance=61)
    assert len(texts) == 1 and "https://git/mr/1" not in texts[0] and "Reason" not in texts[0]


# ── Reasons and return requests (FR-71) ───────────────────────────────────────


@pytest.mark.asyncio
async def test_needs_info_and_cancelled_posts_carry_the_public_reason(
    factories, rig, telegram, clock,
):
    await _enable(rig)
    bug = await _report(factories, rig)
    await _drain(telegram, clock)
    telegram.channel[1:] = []
    resp = await rig["lead_client"].post(f"/issues/{bug.id}/triage", json={
        "outcome": "needs_info", "comment": "Which iOS build was it?",
    })
    assert resp.status_code == 200, resp.text
    texts = await _drain(telegram, clock, advance=61)
    assert len(texts) == 1
    assert "New → Needs info" in texts[0] and "Which iOS build was it?" in texts[0]


@pytest.mark.asyncio
async def test_reject_from_done_posts_the_problem_on_production(
    factories, rig, telegram, clock,
):
    await _enable(rig)
    bug = await _settled(factories, rig, telegram, clock)
    await _move(rig["admin"], bug.id, "in_progress", "in_review", "verified", "done")
    await _drain(telegram, clock, advance=61)
    telegram.channel[1:] = []
    resp = await rig["admin"].post(
        f"/issues/{bug.id}/reject", json={"comment": "Customer still sees the crash."},
    )
    assert resp.status_code == 200, resp.text
    texts = await _drain(telegram, clock, advance=61)
    assert len(texts) == 1
    assert "Done → Rejected" in texts[0]
    assert "Problem on production: Customer still sees the crash." in texts[0]


@pytest.mark.asyncio
async def test_return_request_events_are_posted_with_their_comments(
    factories, rig, telegram, clock,
):
    await _enable(rig)
    bug = await _settled(factories, rig, telegram, clock)
    await _move(rig["admin"], bug.id, "in_progress", "in_review", "verified", "done")
    await _drain(telegram, clock, advance=61)
    telegram.channel[1:] = []

    resp = await rig["support_client"].post(
        f"/issues/{bug.id}/return-requests", json={"comment": "Reproduced on 2.4.1."},
    )
    assert resp.status_code in (200, 201), resp.text
    request_id = resp.json()["id"]
    texts = await _drain(telegram, clock)
    assert len(texts) == 1 and "Reproduced on 2.4.1." in texts[0]

    resp = await rig["lead_client"].post(
        f"/return-requests/{request_id}/dismiss", json={"comment": "Fixed in 2.4.2 already."},
    )
    assert resp.status_code == 200, resp.text
    texts = await _drain(telegram, clock)
    assert len(texts) == 2 and "Fixed in 2.4.2 already." in texts[1]

    resp = await rig["support_client"].post(
        f"/issues/{bug.id}/return-requests", json={"comment": "Back again."},
    )
    request_id = resp.json()["id"]
    await _drain(telegram, clock)
    resp = await rig["lead_client"].post(f"/return-requests/{request_id}/confirm")
    assert resp.status_code == 200, resp.text
    texts = await _drain(telegram, clock, advance=61)
    assert any("Done → Rejected" in t for t in texts[2:])
    assert sum("confirmed" in t.lower() for t in texts[2:]) >= 1


# ── AC-96 — no channel, no post; subscribers unaffected ───────────────────────


@pytest.mark.asyncio
async def test_ac_96_without_an_enabled_channel_nothing_is_posted(
    factories, rig, telegram, clock,
):
    await telegram.link_telegram(rig["support"])
    bug = await _bug(factories, rig)  # never configured
    await _move(rig["admin"], bug.id, "in_progress", "in_review", "verified", "done")
    await _drain(telegram, clock, advance=300)
    assert telegram.channel == []
    assert [t for t, _ in telegram.sent_to(rig["support"])].count("support_done") == 1

    # Configured and tested, but switched off.
    await _enable(rig)
    pid = rig["project"].id
    await rig["cto_client"].put(
        f"/projects/{pid}/support-channel",
        json={"chat_id": CHAT_ID, "thread_id": THREAD_ID, "enabled": False},
    )
    before = len(telegram.channel)
    bug2 = await _bug(factories, rig)
    await _move(rig["admin"], bug2.id, "in_progress")
    await _drain(telegram, clock, advance=300)
    assert len(telegram.channel) == before


@pytest.mark.asyncio
async def test_internal_items_never_produce_posts(factories, rig, telegram, clock):
    await _enable(rig)
    issue = await factories.issue(project_id=rig["project"].id, release_id=rig["stream_id"])
    await _move(rig["admin"], issue.id, "in_progress", "in_review")
    assert await _drain(telegram, clock, advance=300) == []


# ── AC-97 — a Telegram outage never blocks or undoes the action ───────────────


@pytest.mark.asyncio
async def test_ac_97_an_unreachable_chat_retries_then_fails_without_touching_the_item(
    factories, rig, telegram, clock,
):
    await _enable(rig)
    bug = await _settled(factories, rig, telegram, clock)
    telegram.channel_error = "Bad Gateway"

    resp = await rig["admin"].post(f"/issues/{bug.id}/transition", json={"to": "in_progress"})
    assert resp.status_code == 200, resp.text
    assert (await rig["admin"].get(f"/issues/{bug.id}")).json()["status"] == "in_progress"

    clock.advance(seconds=61)
    for _ in range(12):  # the beat keeps coming; each failure backs off
        await send_due_posts(clock())  # never raises
        clock.advance(hours=1)
    state = (await rig["cto_client"].get(f"/projects/{rig['project'].id}/support-channel")).json()
    assert state["failed_posts"] == 1 and state["pending_posts"] == 0
    assert "Bad Gateway" in state["last_error"]
    assert (await rig["admin"].get(f"/issues/{bug.id}")).json()["status"] == "in_progress"

    telegram.channel_error = None
    await send_due_posts(clock())
    assert len(telegram.channel) == 1  # a failed post is not resurrected


@pytest.mark.asyncio
async def test_a_transient_failure_is_retried_and_delivered_once(
    factories, rig, telegram, clock,
):
    await _enable(rig)
    bug = await _settled(factories, rig, telegram, clock)
    await _move(rig["admin"], bug.id, "in_progress")
    telegram.channel_error = "Too Many Requests"
    await _drain(telegram, clock, advance=61)
    assert telegram.channel[1:] == []
    telegram.channel_error = None
    texts = await _drain(telegram, clock, advance=3600)
    assert len(texts) == 1
    assert await _drain(telegram, clock, advance=3600) == texts


# ── AC-98 — internal notes never appear (BR-31) ───────────────────────────────


@pytest.mark.asyncio
async def test_ac_98_internal_notes_never_reach_a_post(factories, rig, telegram, clock):
    await _enable(rig)
    secret = "INTERNAL-ONLY-SECRET"
    bug = await _report(factories, rig)
    resp = await rig["dev_client"].post(
        f"/issues/{bug.id}/timeline", json={"body": secret, "is_internal": True},
    )
    assert resp.status_code in (200, 201), resp.text
    resp = await rig["lead_client"].post(f"/issues/{bug.id}/triage", json={
        "outcome": "needs_info", "comment": "Please send the build number.",
    })
    assert resp.status_code == 200, resp.text
    await _drain(telegram, clock, advance=61)

    other = await _bug(factories, rig)
    await rig["dev_client"].post(
        f"/issues/{other.id}/timeline", json={"body": secret, "is_internal": True},
    )
    await _move(rig["admin"], other.id, "in_progress", "in_review", "verified", "done")
    resp = await rig["admin"].post(
        f"/issues/{other.id}/reject", json={"comment": "Public reason."},
    )
    assert resp.status_code == 200, resp.text
    await _drain(telegram, clock, advance=300)

    assert len(telegram.channel) > 1
    assert all(secret not in text for _, _, text in telegram.channel)


# ── One-way: the bot never answers in a group ─────────────────────────────────


@pytest.mark.asyncio
async def test_the_bot_ignores_group_messages_but_still_answers_private_chats(db_session):
    from app.telegram.handlers import dispatch

    class Recorder:
        def __init__(self):
            self.sent = []

        async def send_message(self, chat_id, text, parse_mode="HTML", message_thread_id=None):
            self.sent.append((chat_id, text))

    client = Recorder()
    for chat_type in ("group", "supergroup", "channel"):
        await dispatch(
            {"chat": {"id": -1002809394924, "type": chat_type}, "from": {"id": 5},
             "text": "/start", "message_thread_id": 7},
            client, db_session,
        )
        await dispatch(
            {"chat": {"id": -1002809394924, "type": chat_type}, "from": {"id": 5},
             "text": "hello everyone"},
            client, db_session,
        )
    assert client.sent == []

    await dispatch({"chat": {"id": 5, "type": "private"}, "from": {"id": 5}, "text": "/start"},
                   client, db_session)
    assert len(client.sent) == 1
