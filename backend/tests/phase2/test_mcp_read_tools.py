"""Slice 16 — MCP read tools.

docs/phase-2/16-mcp-read-tools.md (prd-mcp.md FR-M02–FR-M09, FR-M21–FR-M23,
FR-M36, BR-M03, BR-M16, BR-M17, AC-M03, AC-M05–M08, AC-M12–M14). Every
assertion goes through ``/mcp`` with the in-process MCP client
(``mcp_client_for``); fixtures are built through the REST API. S3 is the
in-memory ``fake_s3``, embeddings and Jev the slice-12/13 fakes, index and
hint jobs run through ``search_jobs``.
"""

import base64
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import text

from app.db.models.issue_timeline import SIGNIFICANT_TIMELINE_EVENTS
from app.db.session import get_engine

KEY = "tsk-test-0123456789abcdef"
REACTION_SEEDED = "ری‌اکشن روی پیام‌های گروه ذخیره نمی‌شود"
REACTION_DRAFT = "ری‌اکشن های گروه بعد از رفرش ذخیره نمی‌شود"
REACTION_OTHER = "شمارنده ری‌اکشن در چت خصوصی اشتباه است"
PAYMENT_SEEDED = "پرداخت در صفحه تسویه با خطا شکست می‌خورد"
CURL = (
    "curl -X POST 'https://api.example.com/v1/chat/react' "
    "-H 'Authorization: Bearer abc.def' -H 'Content-Type: application/json' "
    "--data '{\"emoji\": \"👍\"}'"
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _result(res) -> dict:
    assert not res.is_error, res.content
    assert res.structured_content is not None
    return res.structured_content


def _text(res) -> str:
    return "\n".join(c.text for c in res.content if c.type == "text")


def _error(res) -> str:
    assert res.is_error, res.structured_content
    return res.structured_content["code"]


def _keys(rows) -> list[str]:
    return [r["key"] for r in rows]


async def _move(client, issue_id, *steps):
    for to in steps:
        resp = await client.post(f"/issues/{issue_id}/transition", json={"to": to})
        assert resp.status_code == 200, resp.text


async def _comment(client, issue_id, body, internal=False):
    resp = await client.post(
        f"/issues/{issue_id}/timeline", json={"body": body, "is_internal": internal},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _backdate_completed(issue_id: int, when: datetime) -> None:
    async with get_engine().begin() as conn:
        await conn.execute(
            text("UPDATE issues SET completed_at = :w WHERE id = :i"), {"w": when, "i": issue_id},
        )


async def enable_jev(admin) -> None:
    assert (await admin.put("/settings/search/jev", json={"api_key": KEY})).status_code == 200
    assert (await admin.post("/settings/search/jev/test")).json()["ok"]
    assert (await admin.put("/settings/search/jev", json={"enabled": True})).status_code == 200


def judge_by_family(key: str, question: dict, state) -> dict:
    """``same`` iff draft and candidate are both about reactions or both about
    payments; the settings ping and rerank questions answer 0.9."""
    if question.get("type") != "choice" or "existing_issue" not in question.get("instructions", {}):
        return {"type": "noul", "noul": 0.9}
    existing = question["instructions"]["existing_issue"]["title"]
    draft = state["new_report"]["title"]
    same = any(w in existing and w in draft for w in ("ری‌اکشن", "پرداخت"))
    label = "same" if same else "unrelated"
    return {"type": "choice", "choice": label, "probabilities": {label: 0.9}, "confidence": 0.9}


async def _attach(client, issue_id, fake_s3, *, name, mime, data, size=None):
    """Upload through the attachment API the way the browser does: presign,
    put the bytes in (fake) S3, confirm."""
    presign = await client.post(
        f"/issues/{issue_id}/attachments/presign",
        json={"filename": name, "mime_type": mime, "attachment_type": "screenshot"},
    )
    assert presign.status_code in (200, 201), presign.text
    s3_key = presign.json()["s3_key"]
    fake_s3.put(s3_key, data, mime)
    resp = await client.post(f"/issues/{issue_id}/attachments/confirm", json={
        "s3_key": s3_key, "filename": name, "mime_type": mime,
        "file_size_bytes": size if size is not None else len(data),
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def rig(factories, client_for, mcp_client_for):
    dev = await factories.user(role="developer", name="Dana Dev")
    qa = await factories.user(role="qa", name="Quinn QA")
    project = await factories.project(name="Chat", slug="chat")
    other = await factories.project(name="Payments", slug="payments")
    release = await factories.release(project_id=project.id, version="2.4.0")
    return {
        "admin": factories.admin_client,
        "dev": dev, "dev_client": await client_for(dev),
        "qa": qa, "qa_client": await client_for(qa),
        "project": project, "other": other, "release": release,
        "stream_id": await factories.stream_id(project_id=project.id),
        "mcp": await mcp_client_for(dev),
    }


async def _task(factories, rig, *steps, release_id=None, **overrides):
    task = await factories.issue(
        project_id=overrides.pop("project_id", rig["project"].id), type="task",
        release_id=release_id or rig["stream_id"], **overrides,
    )
    if steps:
        await _move(rig["admin"], task.id, *steps)
    return task


# ── rw_my_queue (FR-M02) ─────────────────────────────────────────────────────


async def test_my_queue_is_in_progress_then_pinned_then_the_rest(factories, rig):
    dev = rig["dev"]
    rest = await _task(factories, rig, assignee_id=dev.id, priority="low", due_date="2030-01-10")
    working = await _task(factories, rig, "in_progress", assignee_id=dev.id)
    pinned = await _task(factories, rig, assignee_id=dev.id, priority="low")
    resp = await rig["dev_client"].post("/users/me/queue/pins", json={"issue_id": pinned.id})
    assert resp.status_code == 200, resp.text
    rejected = await _task(factories, rig, "in_progress", "to_review", assignee_id=dev.id)
    resp = await rig["admin"].post(
        f"/issues/{rejected.id}/reject", json={"comment": "Still spins."},
    )
    assert resp.status_code == 200, resp.text
    await _task(factories, rig, assignee_id=rig["qa"].id)  # someone else's

    res = await rig["mcp"].call("rw_my_queue")
    entries = _result(res)["items"]
    assert _keys(entries)[:2] == [working.key, pinned.key]
    assert set(_keys(entries)[2:]) == {rest.key, rejected.key}
    assert [e["group"] for e in entries[:2]] == ["in_progress", "pinned"]

    by_key = {e["key"]: e for e in entries}
    first = by_key[rest.key]
    assert first["type"] == "task" and first["title"] == rest.title
    assert first["project"] == {"key": "chat", "name": "Chat"}
    assert first["status"] == "todo" and first["priority"] == "low"
    assert first["pinned"] is False and first["due_date"] == "2030-01-10"
    assert first["cycle_number"] == 1
    assert by_key[pinned.key]["pinned"] is True
    assert by_key[rejected.key]["status"] == "rejected"
    assert by_key[rejected.key]["cycle_number"] == 2
    # Clients that show only text still read the queue.
    assert working.key in _text(res) and rest.title in _text(res)


# ── rw_get_item (FR-M03) ─────────────────────────────────────────────────────


async def test_get_item_by_key_any_case_with_every_field(factories, rig):
    bug = await factories.issue(
        project_id=rig["project"].id, release_id=rig["release"].id,
        title="Reactions vanish after refresh", description="Seen in **group** chats.",
        curl_command=CURL,
        reproduction_steps=[{
            "step_order": 1, "description": "React to a message",
            "expected_result": "It stays", "actual_result": "Gone after refresh",
        }],
        environment_browser="Chrome 130", environment_os="macOS 15",
        environment_build_hash="abc1234", environment_name="staging",
        environment_staging_url="https://staging.example.com",
        assignee_id=rig["dev"].id, priority="high",
    )
    n = bug.issue_number
    for key in (f"BUG-{n}", f"bug-{n}", f"issue-{n}", f"Bug-{n}"):
        res = await rig["mcp"].call("rw_get_item", {"key": key})
        assert _result(res)["key"] == f"BUG-{n}", key

    item = _result(res)
    assert item["title"] == "Reactions vanish after refresh"
    assert item["description"] == "Seen in **group** chats."
    assert item["curl_command"] == CURL  # the full command, headers included
    assert item["reproduction_steps"][0]["actual_result"] == "Gone after refresh"
    assert item["environment"] == {
        "name": "staging", "browser": "Chrome 130", "os": "macOS 15",
        "build_hash": "abc1234", "staging_url": "https://staging.example.com",
    }
    assert item["project"] == {"key": "chat", "name": "Chat"}
    assert item["container"]["kind"] == "release" and item["container"]["name"] == "2.4.0"
    assert item["assignee"]["username"] == rig["dev"].username
    assert item["status"] == "todo" and item["type"] == "bug" and item["priority"] == "high"
    assert item["reject"] is None
    md = _text(res)
    assert "Reactions vanish after refresh" in md and "Authorization: Bearer abc.def" in md


async def test_get_item_shows_the_stream_as_its_container(factories, rig):
    task = await _task(factories, rig)
    item = _result(await rig["mcp"].call("rw_get_item", {"key": task.key}))
    assert item["container"]["kind"] == "stream"
    backlog = await factories.issue(project_id=rig["project"].id, type="task")
    assert _result(await rig["mcp"].call("rw_get_item", {"key": backlog.key}))["container"] is None


async def test_ac_m03_unknown_deleted_or_malformed_key_is_not_found(factories, rig):
    gone = await _task(factories, rig)
    assert (await rig["admin"].delete(f"/issues/{gone.id}")).status_code == 204
    for key in (gone.key, "BUG-999999", "hello", "PR-12", ""):
        res = await rig["mcp"].call("rw_get_item", {"key": key})
        assert _error(res) == "not_found", key
        assert res.content[0].text  # a sentence the agent can relay


async def test_ac_m06_rejected_item_has_reject_comment_and_start_reason(factories, rig):
    task = await _task(factories, rig, "in_progress", "to_review", assignee_id=rig["dev"].id)
    resp = await rig["qa_client"].post(
        f"/issues/{task.id}/reject", json={"comment": "The empty state still shows the spinner."},
    )
    assert resp.status_code == 200, resp.text

    res = await rig["mcp"].call("rw_get_item", {"key": task.key})
    item = _result(res)
    assert item["status"] == "rejected"
    assert item["reject"]["reason"] == "review"
    assert item["reject"]["comment"]["body"] == "The empty state still shows the spinner."
    assert item["reject"]["comment"]["author"]["username"] == rig["qa"].username
    assert [(c["number"], c["start_reason"]) for c in item["cycles"]] == [
        (1, "planned"), (2, "review"),
    ]
    assert item["cycles"][0]["closed_at"] is not None
    assert "The empty state still shows the spinner." in _text(res)


async def test_ac_m07_default_timeline_is_comments_and_significant_events(
    factories, rig, monkeypatch,
):
    from app.mcp_server import read_tools

    monkeypatch.setattr(read_tools, "_TIMELINE_PAGE", 7)  # pagination stays internal
    task = await _task(factories, rig, assignee_id=rig["dev"].id)
    await _comment(rig["admin"], task.id, "First public comment.")
    await _comment(rig["dev_client"], task.id, "Root cause is the cache key.", internal=True)
    await _comment(rig["qa_client"], task.id, "Reproduced on staging.")
    for day in range(40):
        due = (date(2030, 1, 1) + timedelta(days=day)).isoformat()
        resp = await rig["admin"].patch(f"/issues/{task.id}", json={"due_date": due})
        assert resp.status_code == 200, resp.text
    await _move(rig["admin"], task.id, "in_progress")

    default = _result(await rig["mcp"].call("rw_get_item", {"key": task.key}))
    assert default["full_timeline"] is False
    types = [e["type"] for e in default["timeline"]]
    assert set(types) <= {t.value for t in SIGNIFICANT_TIMELINE_EVENTS}
    assert types.count("comment") == 3
    assert "status_changed" in types and "due_date_changed" not in types

    note = next(e for e in default["timeline"] if e["internal"])
    assert note["body"] == "Root cause is the cache key."
    assert note["author"]["username"] == rig["dev"].username
    assert note["at"] and note["via_agent"] is False

    full = _result(await rig["mcp"].call("rw_get_item", {"key": task.key, "full_timeline": True}))
    assert full["full_timeline"] is True
    full_types = [e["type"] for e in full["timeline"]]
    assert full_types.count("due_date_changed") == 40
    rest_total = (await rig["dev_client"].get(f"/issues/{task.id}/timeline")).json()["total"]
    assert len(full["timeline"]) == rest_total > 7 * 5


async def test_get_item_lists_attachments_and_cycles(factories, rig, fake_s3):
    task = await _task(factories, rig)
    await _attach(rig["qa_client"], task.id, fake_s3, name="spinner.png", mime="image/png",
                  data=b"\x89PNG fake")
    item = _result(await rig["mcp"].call("rw_get_item", {"key": task.key}))
    [att] = item["attachments"]
    assert att["file_name"] == "spinner.png" and att["mime_type"] == "image/png"
    assert att["size"] == len(b"\x89PNG fake")
    assert att["author"]["username"] == rig["qa"].username
    assert att["via_agent"] is False and isinstance(att["id"], int)
    assert [c["start_reason"] for c in item["cycles"]] == ["planned"]


async def test_developer_reads_an_item_found_only_through_an_internal_note(
    factories, rig, search_jobs,
):
    """Internal notes are visible to tech roles, so an item matched only through
    one is found and read in full."""
    task = await _task(factories, rig, title="Nightly export job")
    note = "Redis connection pool exhausted when the payment webhook retries in a burst"
    await _comment(rig["admin"], task.id, note, internal=True)
    await search_jobs.run()

    found = _result(
        await rig["mcp"].call("rw_search", {"query": "redis connection pool exhausted"}),
    )
    assert task.key in _keys(found["results"])
    item = _result(await rig["mcp"].call("rw_get_item", {"key": task.key}))
    assert any(e["internal"] and e["body"] == note for e in item["timeline"])


# ── rw_get_attachment (FR-M04, AC-M05) ───────────────────────────────────────


async def test_ac_m05_image_inline(factories, rig, fake_s3):
    task = await _task(factories, rig)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024)
    att = await _attach(rig["qa_client"], task.id, fake_s3, name="screen.png",
                        mime="image/png", data=png)

    res = await rig["mcp"].call("rw_get_attachment", {"key": task.key, "attachment_id": att["id"]})
    assert not res.is_error
    [image] = [c for c in res.content if c.type == "image"]
    assert image.mime_type == "image/png"
    assert base64.b64decode(image.data) == png
    assert res.structured_content["file_name"] == "screen.png"
    assert res.structured_content.get("download_url") is None


async def test_ac_m05_large_file_link(factories, rig, fake_s3, clock):
    now = datetime.now(UTC).replace(microsecond=0)
    clock.set(now)
    task = await _task(factories, rig)
    video = await _attach(rig["qa_client"], task.id, fake_s3, name="repro.mp4",
                          mime="video/mp4", data=b"tiny", size=40 * 1024 * 1024)
    big_png = await _attach(rig["qa_client"], task.id, fake_s3, name="huge.png",
                            mime="image/png", data=b"x" * 16, size=6 * 1024 * 1024)
    log = await _attach(rig["qa_client"], task.id, fake_s3, name="server.log",
                        mime="text/plain", data=b"boom")

    for att, name, mime in (
        (video, "repro.mp4", "video/mp4"), (big_png, "huge.png", "image/png"),
        (log, "server.log", "text/plain"),
    ):
        res = await rig["mcp"].call(
            "rw_get_attachment", {"key": task.key, "attachment_id": att["id"]},
        )
        body = _result(res)
        assert not [c for c in res.content if c.type == "image"], name
        assert body["download_url"].startswith("https://fake-s3.test/")
        assert body["file_name"] == name and body["mime_type"] == mime
        assert body["size"] == att["file_size_bytes"]
        expires = datetime.fromisoformat(body["expires_at"])
        assert now < expires <= now + timedelta(hours=1)
        assert body["download_url"] in _text(res)
    assert fake_s3.reads == []  # only small images are ever read by the server


async def test_attachment_of_another_item_is_attachment_not_found(factories, rig, fake_s3):
    one = await _task(factories, rig)
    two = await _task(factories, rig)
    att = await _attach(
        rig["qa_client"], one.id, fake_s3, name="a.png", mime="image/png", data=b"a",
    )
    res = await rig["mcp"].call("rw_get_attachment", {"key": two.key, "attachment_id": att["id"]})
    assert _error(res) == "attachment_not_found"
    res = await rig["mcp"].call(
        "rw_get_attachment", {"key": "TASK-999999", "attachment_id": att["id"]},
    )
    assert _error(res) == "not_found"


# ── rw_search (FR-M05, AC-M08) ───────────────────────────────────────────────


@pytest.fixture
async def reactions(factories, rig, search_jobs):
    items = {
        "chat": await _task(factories, rig, title=REACTION_SEEDED),
        "payments": await factories.issue(
            project_id=rig["other"].id, type="task", title=REACTION_OTHER,
        ),
        "cancelled": await _task(factories, rig, "cancelled", title=REACTION_DRAFT),
    }
    await search_jobs.run()
    return items


async def test_ac_m08_search_without_project_covers_every_visible_project(rig, reactions):
    res = await rig["mcp"].call("rw_search", {"query": "ری‌اکشن"})
    body = _result(res)
    found = _keys(body["results"])
    assert {reactions["chat"].key, reactions["payments"].key} <= set(found)
    assert body["jev_used"] is False and body["less_relevant"] == []
    assert reactions["chat"].key in _text(res)

    scoped = _result(await rig["mcp"].call("rw_search", {"query": "ری‌اکشن", "project": "CHAT"}))
    assert reactions["payments"].key not in _keys(scoped["results"])
    assert reactions["chat"].key in _keys(scoped["results"])
    for row in scoped["results"]:
        assert row["project"]["key"] == "chat"


async def test_search_marks_cancelled_items_and_filters(rig, reactions):
    body = _result(await rig["mcp"].call("rw_search", {"query": "ری‌اکشن"}))
    by_key = {r["key"]: r for r in body["results"]}
    assert by_key[reactions["cancelled"].key]["is_cancelled"] is True
    assert by_key[reactions["chat"].key]["is_cancelled"] is False

    only_open = _result(await rig["mcp"].call(
        "rw_search", {"query": "ری‌اکشن", "status": ["todo"], "type": ["task"]},
    ))
    assert reactions["cancelled"].key not in _keys(only_open["results"])


async def test_search_unknown_project_is_not_found(rig):
    res = await rig["mcp"].call("rw_search", {"query": "x", "project": "nope"})
    assert _error(res) == "not_found"


async def test_search_with_jev_returns_less_relevant_separately(rig, reactions, jev):
    await enable_jev(rig["admin"])
    scores = {reactions["chat"].id: 0.93, reactions["payments"].id: 0.2,
              reactions["cancelled"].id: 0.1}
    jev.default(lambda key, q, state: {"type": "noul", "noul": scores[int(key[2:])]})
    body = _result(await rig["mcp"].call("rw_search", {"query": "ری‌اکشن"}))
    assert body["jev_used"] is True
    assert _keys(body["results"]) == [reactions["chat"].key]
    assert set(_keys(body["less_relevant"])) == {
        reactions["payments"].key, reactions["cancelled"].key,
    }


# ── rw_find_similar (FR-M21–M23, AC-M12–M14) ─────────────────────────────────


@pytest.fixture
async def duplicates(factories, rig, search_jobs):
    """The same problem in another project, a cancelled copy, and an unrelated item."""
    items = {
        "neighbour": await factories.issue(
            project_id=rig["other"].id, type="task", title=REACTION_SEEDED,
        ),
        "cancelled": await _task(factories, rig, "cancelled", title=REACTION_SEEDED),
        "payment": await _task(factories, rig, title=PAYMENT_SEEDED),
    }
    await search_jobs.run()
    return items


async def test_ac_m12_jev_on_finds_same_problem_in_another_project(rig, duplicates, jev):
    await enable_jev(rig["admin"])
    jev.default(judge_by_family)
    res = await rig["mcp"].call(
        "rw_find_similar", {"type": "bug", "title": REACTION_DRAFT, "description": "بعد از رفرش"},
    )
    body = _result(res)
    assert body["jev_used"] is True
    [hit] = body["items"]
    assert hit["issue"]["key"] == duplicates["neighbour"].key
    assert hit["issue"]["project"]["key"] == "payments"
    assert hit["verdict"] == "same" and hit["confidence"] >= 0.74
    assert duplicates["neighbour"].key in _text(res)


async def test_ac_m13_jev_off_returns_local_candidates_without_verdicts(rig, duplicates, jev):
    res = await rig["mcp"].call("rw_find_similar", {"type": "bug", "title": REACTION_DRAFT})
    body = _result(res)
    assert body["jev_used"] is False
    keys = [i["issue"]["key"] for i in body["items"]]
    assert duplicates["neighbour"].key in keys
    assert duplicates["payment"].key not in keys  # under the minimum similarity
    assert len(keys) <= 5
    for row in body["items"]:
        assert row.get("verdict") is None and row.get("confidence") is None
    assert jev.calls == []


async def test_jev_failing_falls_back_to_local_candidates(rig, duplicates, jev):
    await enable_jev(rig["admin"])
    jev.fail("http_500")
    res = await rig["mcp"].call("rw_find_similar", {"type": "bug", "title": REACTION_DRAFT})
    body = _result(res)
    assert body["jev_used"] is False
    assert duplicates["neighbour"].key in [i["issue"]["key"] for i in body["items"]]


async def test_ac_m14_cancelled_is_never_a_candidate(rig, duplicates, jev):
    for enabled in (False, True):
        if enabled:
            await enable_jev(rig["admin"])
        body = _result(await rig["mcp"].call(
            "rw_find_similar", {"type": "task", "title": REACTION_SEEDED},
        ))
        keys = [i["issue"]["key"] for i in body["items"]]
        assert duplicates["cancelled"].key not in keys, enabled
        assert duplicates["neighbour"].key in keys, enabled


# ── rw_triage_queue (FR-M07) ─────────────────────────────────────────────────


async def test_triage_queue_lists_new_and_needs_info_bugs_with_possible_duplicates(
    factories, rig, search_jobs, jev,
):
    await enable_jev(rig["admin"])
    jev.default(judge_by_family)
    original = await _task(factories, rig, title=REACTION_SEEDED)
    first = await factories.issue(
        project_id=rig["project"].id, title=REACTION_DRAFT, client=rig["qa_client"],
    )
    second = await factories.issue(project_id=rig["project"].id, title="Login button misaligned")
    resp = await rig["admin"].post(
        f"/issues/{second.id}/triage", json={"outcome": "needs_info", "comment": "Which page?"},
    )
    assert resp.status_code == 200, resp.text
    accepted = await factories.issue(project_id=rig["project"].id, title="Accepted already")
    resp = await rig["admin"].post(f"/issues/{accepted.id}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": rig["stream_id"],
    })
    assert resp.status_code == 200, resp.text
    await factories.issue(project_id=rig["other"].id, title="Elsewhere")
    await search_jobs.run()

    res = await rig["mcp"].call("rw_triage_queue", {"project": "chat"})
    body = _result(res)
    assert _keys(body["items"]) == [first.key, second.key]  # oldest first
    row = body["items"][0]
    assert row["status"] == "new" and row["source"] == "internal"
    assert row["reporter"]["username"] == rig["qa"].username
    assert row["recurrence_count"] == 1
    [hint] = row["possible_duplicates"]
    assert hint["key"] == original.key and hint["merge_effect"] == "unchanged"
    assert body["items"][1]["status"] == "needs_info"
    assert body["items"][1]["possible_duplicates"] == []
    assert first.key in _text(res)

    await rig["admin"].put("/settings/search/jev", json={"enabled": False})
    body = _result(await rig["mcp"].call("rw_triage_queue", {"project": "chat"}))
    assert body["items"][0]["possible_duplicates"] == []
    assert _error(await rig["mcp"].call("rw_triage_queue", {"project": "nope"})) == "not_found"


# ── rw_board (FR-M08) ────────────────────────────────────────────────────────


async def test_board_without_release_is_the_stream_with_done_limited_to_7_days(
    factories, rig, clock,
):
    now = datetime.now(UTC).replace(microsecond=0)
    clock.set(now)
    todo = await _task(factories, rig)
    recent = await _task(factories, rig, "done")
    await _backdate_completed(recent.id, now - timedelta(days=2))
    old = await _task(factories, rig, "done")
    await _backdate_completed(old.id, now - timedelta(days=10))
    await _task(factories, rig, release_id=rig["release"].id)  # not in the Stream

    res = await rig["mcp"].call("rw_board", {"project": "chat"})
    body = _result(res)
    assert body["container"]["kind"] == "stream"
    assert datetime.fromisoformat(body["done_from"]) == now - timedelta(days=7)
    cols = {c["status"]: _keys(c["items"]) for c in body["columns"]}
    assert cols["todo"] == [todo.key]
    assert cols["done"] == [recent.key]
    assert todo.key in _text(res)


async def test_board_with_release_has_the_header(factories, rig, clock):
    now = datetime.now(UTC).replace(microsecond=0)
    clock.set(now)
    rid = rig["release"].id
    resp = await rig["admin"].patch(
        f"/releases/{rid}", json={"target_date": (now - timedelta(days=3)).isoformat()},
    )
    assert resp.status_code == 200, resp.text
    blocker = await factories.issue(
        project_id=rig["project"].id, release_id=rid, title="Crash on send",
        is_release_blocker=True,
    )
    done = await _task(factories, rig, "done", release_id=rid)
    await _task(factories, rig, release_id=rid)

    res = await rig["mcp"].call("rw_board", {"project": "chat", "release": "2.4.0"})
    body = _result(res)
    header = body["container"]
    assert header["kind"] == "release" and header["name"] == "2.4.0"
    assert header["status"] == "planning"
    assert header["is_overdue"] is True
    assert header["progress"] == pytest.approx(1 / 3)
    assert header["go_nogo"]["status"]
    assert _keys(header["open_blockers"]) == [blocker.key]
    cols = {c["status"]: _keys(c["items"]) for c in body["columns"]}
    assert cols["done"] == [done.key] and cols["new"] == [blocker.key]
    assert "2.4.0" in _text(res)

    for project, version in (("chat", "9.9"), ("payments", "2.4.0")):
        res = await rig["mcp"].call("rw_board", {"project": project, "release": version})
        assert _error(res) == "not_found", (project, version)


# ── rw_tech_debt (FR-M09) ────────────────────────────────────────────────────


async def test_tech_debt_with_filters(factories, rig):
    dev = rig["dev"]
    mine = await factories.issue(project_id=rig["project"].id, type="task", is_tech_debt=True,
                                 assignee_id=dev.id, title="Drop the legacy cache")
    unowned = await factories.issue(project_id=rig["project"].id, type="task", is_tech_debt=True,
                                    title="Split the chat service")
    await _move(rig["admin"], unowned.id, "done")
    elsewhere = await factories.issue(project_id=rig["other"].id, type="task", is_tech_debt=True,
                                      assignee_id=dev.id)
    await factories.issue(project_id=rig["project"].id, type="task")  # not debt

    async def debt(**args):
        res = await rig["mcp"].call("rw_tech_debt", args)
        return set(_keys(_result(res)["items"])), res

    keys, res = await debt()
    assert keys == {mine.key, unowned.key, elsewhere.key}
    assert mine.title in _text(res)
    assert (await debt(project="chat"))[0] == {mine.key, unowned.key}
    assert (await debt(assignee=dev.username))[0] == {mine.key, elsewhere.key}
    assert (await debt(project="chat", status=["todo"]))[0] == {mine.key}
    assert _error(await rig["mcp"].call("rw_tech_debt", {"assignee": "nobody-here"})) == "not_found"


# ── Resource rw://item/{key} (FR-M36) ────────────────────────────────────────


async def test_item_resource_is_the_default_context_as_markdown(factories, rig):
    bug = await factories.issue(
        project_id=rig["project"].id, title="Reactions vanish", curl_command=CURL,
    )
    await _comment(rig["qa_client"], bug.id, "Happens on Android too.")
    tool_md = _text(await rig["mcp"].call("rw_get_item", {"key": bug.key}))

    res = await rig["mcp"].call(f"rw://item/{bug.key.lower()}")
    [content] = res.contents
    assert content.mime_type == "text/markdown"
    assert content.text == tool_md
    assert "Reactions vanish" in content.text and "Happens on Android too." in content.text


# ── Errors and the gate ──────────────────────────────────────────────────────


async def test_read_tools_are_behind_the_kill_switch(factories, rig):
    assert (await rig["admin"].put("/settings/mcp", json={"enabled": False})).status_code == 200
    refusal = await rig["mcp"].refusal("rw_my_queue")
    assert refusal.code == "mcp_disabled"


async def test_every_read_tool_is_listed():
    from app.mcp_server.server import server

    names = {t.name for t in await server.list_tools()}
    assert {
        "rw_context", "rw_my_queue", "rw_get_item", "rw_get_attachment", "rw_search",
        "rw_find_similar", "rw_triage_queue", "rw_board", "rw_tech_debt",
    } <= names
