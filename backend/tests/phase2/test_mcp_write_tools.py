"""Slice 17 — agent origin and the MCP write tools.

docs/phase-2/17-mcp-agent-origin-and-write-tools.md (prd-mcp.md FR-M10–FR-M24,
FR-M29, FR-M30, BR-M01, BR-M05, BR-M06, BR-M08–M13, BR-M15, BR-M16, BR-M19,
AC-M01, AC-M09–M11, AC-M15–M26, AC-M34, AC-M35). Tools are driven through
``/mcp`` with the in-process MCP client; what they wrote is read back through
``/api/v1``. ``fake_s3`` stands in for the agent's upload: the test writes the
object at the presigned key.
"""

import pytest

from tests.phase2.test_mcp_read_tools import (
    REACTION_DRAFT,
    REACTION_SEEDED,
    _error,
    _result,
    _text,
)

READ_TOOLS = {
    "rw_context", "rw_my_queue", "rw_get_item", "rw_get_attachment", "rw_search",
    "rw_find_similar", "rw_triage_queue", "rw_board", "rw_tech_debt",
}
WRITE_TOOLS = {
    "rw_upload_prepare", "rw_file_bug", "rw_file_tech_debt", "rw_add_note", "rw_attach",
    "rw_fill_field", "rw_report_recurrence",
}
#: Slice 18: content the agent owns.
OWN_TOOLS = {"rw_update_own", "rw_delete_own"}
BUG_TITLE = "Chat reactions disappear after a page refresh"
DEBT_TITLE = "Replace the hand-written retry loop in the S3 client"


# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def rig(factories, client_for, mcp_client_for):
    lead = await factories.user(role="qa", name="Tara Triage")
    dev = await factories.user(role="developer", name="Dana Dev", username="dana")
    qa = await factories.user(role="qa", name="Quinn QA", username="quinn")
    support = await factories.user(role="support", name="Sam Support")
    project = await factories.project(name="Chat", slug="chat", triage_lead_id=lead.id)
    return {
        "admin": factories.admin_client,
        "lead": lead, "lead_client": await client_for(lead),
        "dev": dev, "dev_client": await client_for(dev),
        "qa": qa, "qa_client": await client_for(qa),
        "support": support, "support_client": await client_for(support),
        "project": project,
        "stream_id": await factories.stream_id(project_id=project.id),
        "mcp": await mcp_client_for(dev),
    }


async def _upload(mcp, fake_s3, name="kibana-chat-errors-20261014.log", mime="text/plain",
                  data=b"ERROR reaction lost\n") -> str:
    """Prepare an upload and play the agent's shell: put the bytes at the key."""
    body = _result(await mcp.call(
        "rw_upload_prepare", {"file_name": name, "mime_type": mime, "size": len(data)},
    ))
    fake_s3.put(body["post"]["fields"]["key"], data, mime)
    return body["upload_id"]


async def _file_bug(rig, **args) -> dict:
    return _result(await rig["mcp"].call(
        "rw_file_bug", {"project": "chat", "title": BUG_TITLE, **args},
    ))


async def _get(client, issue_key_or_id) -> dict:
    if isinstance(issue_key_or_id, str):
        number = issue_key_or_id.split("-")[1]
        resp = await client.get(f"/issues/by-number/{number}")
    else:
        resp = await client.get(f"/issues/{issue_key_or_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _timeline(client, issue_id) -> list[dict]:
    resp = await client.get(f"/issues/{issue_id}/timeline", params={"size": 200})
    assert resp.status_code == 200, resp.text
    return resp.json()["items"]


async def _attachments(client, issue_id) -> list[dict]:
    resp = await client.get(f"/issues/{issue_id}/attachments")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _inbox_types(client) -> list[str]:
    return [i["type"] for i in (await client.get("/inbox", params={"size": 100})).json()["items"]]


async def _queue_ids(client, user) -> list[int]:
    groups = (await client.get(f"/users/{user.id}/queue")).json()["groups"]
    return [e["issue"]["id"] for g in ("pinned", "rest") for e in groups[g]]


async def _bug(factories, rig, *steps, **overrides):
    """A bug the developer's agent did not file, accepted to To do in the Stream."""
    bug = await factories.issue(
        project_id=rig["project"].id, release_id=rig["stream_id"],
        assignee_id=rig["qa"].id, priority="high", **overrides,
    )
    for to in steps:
        resp = await rig["admin"].post(f"/issues/{bug.id}/transition", json={"to": to})
        assert resp.status_code == 200, resp.text
    return bug


# ── Boundaries (BR-M01, AC-M01) ──────────────────────────────────────────────


async def test_ac_m01_the_server_offers_exactly_these_eighteen_tools(rig):
    names = {t.name for t in await rig["mcp"].tools()}
    assert names == READ_TOOLS | WRITE_TOOLS | OWN_TOOLS
    assert len(names) == 18


async def test_ac_m01_write_tools_change_no_placement_status_flags_or_queue(
    factories, rig, fake_s3,
):
    bug = await _bug(factories, rig, labels=["chat"])
    fields = ("status", "release_id", "labels", "is_release_blocker", "is_tech_debt",
              "assignee_id", "priority", "project_id", "backlog_category_id")
    before = await _get(rig["admin"], bug.id)
    queue_before = await _queue_ids(rig["qa_client"], rig["qa"])
    assert bug.id in queue_before
    mcp = rig["mcp"]

    _result(await mcp.call("rw_add_note", {"key": bug.key, "body": "PR: https://git/pr/12"}))
    upload_id = await _upload(mcp, fake_s3)
    _result(await mcp.call("rw_attach", {"key": bug.key, "upload_id": upload_id}))
    _result(await mcp.call("rw_fill_field", {"key": bug.key, "field": "curl", "value": "curl x"}))
    _result(await mcp.call("rw_fill_field", {
        "key": bug.key, "field": "reproduction_steps", "value": [{"description": "Open chat"}],
    }))
    _result(await mcp.call("rw_fill_field", {
        "key": bug.key, "field": "environment", "value": {"browser": "Firefox 131"},
    }))
    _result(await mcp.call("rw_report_recurrence", {"key": bug.key, "comment": "Again today."}))

    after = await _get(rig["admin"], bug.id)
    assert {f: after[f] for f in fields} == {f: before[f] for f in fields}
    assert await _queue_ids(rig["qa_client"], rig["qa"]) == queue_before


async def test_ac_m01_filing_sets_only_the_fixed_placement(rig):
    bug = await _get(rig["admin"], (await _file_bug(rig, assignee="quinn"))["key"])
    assert bug["status"] == "new" and bug["release_id"] is None
    assert bug["priority"] is None and bug["labels"] == []
    assert bug["is_release_blocker"] is False and bug["is_tech_debt"] is False
    assert bug["assignee_id"] == rig["qa"].id  # asked for — the one thing a filing may set


# ── The agent mark (BR-M05, A.3) ─────────────────────────────────────────────


async def test_every_row_a_tool_writes_is_agent_content_and_the_web_app_writes_none(
    factories, rig, fake_s3,
):
    mcp = rig["mcp"]
    filed = await _file_bug(rig, upload_ids=[await _upload(mcp, fake_s3)])
    issue = await _get(rig["admin"], filed["key"])
    assert issue["via_agent"] is True
    events = await _timeline(rig["admin"], issue["id"])
    assert {e["event_type"] for e in events} >= {"filed"}
    assert all(e["via_agent"] for e in events)
    assert all(a["via_agent"] for a in await _attachments(rig["admin"], issue["id"]))

    bug = await _bug(factories, rig)
    seen = {e["id"] for e in await _timeline(rig["admin"], bug.id)}
    _result(await mcp.call("rw_add_note", {"key": bug.key, "body": "Root cause is the cache."}))
    _result(await mcp.call("rw_attach", {"key": bug.key, "upload_id": await _upload(mcp, fake_s3)}))
    _result(await mcp.call("rw_fill_field", {"key": bug.key, "field": "curl", "value": "curl y"}))
    _result(await mcp.call("rw_report_recurrence", {"key": bug.key, "comment": "Seen again."}))
    new_events = [e for e in await _timeline(rig["admin"], bug.id) if e["id"] not in seen]
    assert {e["event_type"] for e in new_events} >= {"comment", "curl_changed", "recurrence"}
    assert all(e["via_agent"] for e in new_events)
    assert all(a["via_agent"] for a in await _attachments(rig["admin"], bug.id))
    assert (await _get(rig["admin"], bug.id))["via_agent"] is False  # not filed by the agent

    # The same actions through /api/v1 are people's content.
    human = await factories.issue(project_id=rig["project"].id, client=rig["dev_client"])
    resp = await rig["dev_client"].post(
        f"/issues/{human.id}/timeline", json={"body": "A note.", "is_internal": True},
    )
    assert resp.status_code == 201 and resp.json()["via_agent"] is False
    resp = await rig["dev_client"].patch(f"/issues/{human.id}", json={"curl_command": "curl z"})
    assert resp.status_code == 200, resp.text
    assert (await _get(rig["admin"], human.id))["via_agent"] is False
    assert not any(e["via_agent"] for e in await _timeline(rig["admin"], human.id))


async def test_no_request_can_set_or_clear_the_mark(rig):
    filed = await _file_bug(rig)
    issue = await _get(rig["admin"], filed["key"])
    resp = await rig["admin"].patch(f"/issues/{issue['id']}", json={
        "title": "Reactions disappear after a refresh in group chats",
        "via_agent": False, "via_mcp_token_id": None,
    })
    assert resp.status_code == 200, resp.text
    assert resp.json()["via_agent"] is True

    human = await rig["dev_client"].post("/issues", json={
        "project_id": rig["project"].id, "title": "Typed by a person",
        "via_agent": True, "via_mcp_token_id": 1,
    })
    assert human.status_code == 201, human.text
    assert human.json()["via_agent"] is False


async def test_ac_m34_the_badge_stays_when_labels_are_removed(rig):
    filed = await _file_bug(rig)
    issue = await _get(rig["admin"], filed["key"])
    resp = await rig["admin"].patch(f"/issues/{issue['id']}", json={"labels": ["chat"]})
    assert resp.status_code == 200, resp.text
    resp = await rig["admin"].patch(f"/issues/{issue['id']}", json={"labels": []})
    assert resp.status_code == 200, resp.text
    assert resp.json()["via_agent"] is True and resp.json()["labels"] == []


# ── Filing (FR-M11–M15) ──────────────────────────────────────────────────────


async def test_ac_m09_a_filed_bug_enters_triage_and_notifies_the_triage_lead(rig):
    filed = await _file_bug(
        rig,
        description="Reactions in group chats are gone after a refresh.",
        reproduction_steps=[
            {"description": "React to a message", "expected_result": "It stays",
             "actual_result": "It is gone after refresh"},
            {"description": "Refresh the page"},
        ],
        curl="curl -X POST https://api.example.com/v1/react",
        environment={"name": "staging", "browser": "Chrome 130"},
    )
    assert filed["status"] == "new" and filed["via_agent"] is True
    assert filed["url"].endswith(f"/issue/{filed['key'].lower()}")
    assert "#" not in filed["url"]
    bug = await _get(rig["admin"], filed["key"])
    assert bug["type"] == "bug" and bug["status"] == "new"
    assert bug["release_id"] is None and bug["source"] == "internal"
    assert bug["priority"] is None and bug["via_agent"] is True
    assert bug["reporter_id"] == rig["dev"].id
    assert [s["step_order"] for s in bug["reproduction_steps"]] == [1, 2]
    assert bug["curl_command"].startswith("curl -X POST")
    assert bug["environment_name"] == "staging" and bug["environment_browser"] == "Chrome 130"

    queue = (await rig["lead_client"].get("/issues", params={
        "project_id": rig["project"].id, "statuses": "new,needs_info",
    })).json()["items"]
    assert bug["id"] in [i["id"] for i in queue]
    assert "filed" in await _inbox_types(rig["lead_client"])
    assert await factories_cycles(rig, bug["id"]) == []


async def factories_cycles(rig, issue_id) -> list:
    resp = await rig["admin"].get(f"/issues/{issue_id}/cycles")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_a_bug_with_an_assignee_still_enters_triage(rig):
    filed = await _file_bug(rig, assignee="@quinn")
    bug = await _get(rig["admin"], filed["key"])
    assert bug["status"] == "new" and bug["priority"] is None
    assert bug["assignee_id"] == rig["qa"].id


async def test_ac_m10_a_filed_tech_debt_task_is_in_the_backlog(factories, rig):
    filed = _result(await rig["mcp"].call(
        "rw_file_tech_debt", {"project": "chat", "title": DEBT_TITLE},
    ))
    task = await _get(rig["admin"], filed["key"])
    default = await factories.default_category(project_id=rig["project"].id)
    assert task["type"] == "task" and task["status"] == "todo"
    assert task["release_id"] is None and task["backlog_category_id"] == default.id
    assert task["is_tech_debt"] is True and task["priority"] == "medium"
    assert task["assignee_id"] is None and task["via_agent"] is True
    assert await factories_cycles(rig, task["id"]) == []
    backlog = (await rig["admin"].get(
        f"/projects/{rig['project'].id}/backlog", params={"include_tech_debt": True},
    )).json()["items"]
    assert task["id"] in [i["id"] for i in backlog]
    assert "technical debt" in _text(await rig["mcp"].call("rw_get_item", {"key": filed["key"]}))


async def test_a_tech_debt_task_takes_a_confirmed_priority_and_assignee_into_their_queue(rig):
    filed = _result(await rig["mcp"].call("rw_file_tech_debt", {
        "project": "chat", "title": DEBT_TITLE, "priority": "high", "assignee": "quinn",
    }))
    task = await _get(rig["admin"], filed["key"])
    assert task["priority"] == "high" and task["assignee_id"] == rig["qa"].id
    assert task["id"] in await _queue_ids(rig["qa_client"], rig["qa"])


async def test_an_unassignable_or_unknown_assignee_is_refused(rig):
    res = await rig["mcp"].call(
        "rw_file_bug", {"project": "chat", "title": BUG_TITLE, "assignee": rig["support"].username},
    )
    assert _error(res) == "not_assignable"
    res = await rig["mcp"].call(
        "rw_file_bug", {"project": "chat", "title": BUG_TITLE, "assignee": "nobody-here"},
    )
    assert _error(res) == "not_found"
    res = await rig["mcp"].call("rw_file_bug", {"project": "nope", "title": BUG_TITLE})
    assert _error(res) == "not_found"
    total = (await rig["admin"].get("/issues", params={"project_id": rig["project"].id})).json()
    assert total["total"] == 0


async def test_ac_m11_candidates_stop_the_filing_until_file_anyway(factories, rig, search_jobs):
    seeded = await factories.issue(
        project_id=rig["project"].id, type="task", title=REACTION_SEEDED,
    )
    await search_jobs.run()
    args = {"project": "chat", "title": REACTION_DRAFT}

    res = await rig["mcp"].call("rw_file_bug", args)
    assert _error(res) == "duplicates_found"
    body = res.structured_content
    assert body["jev_used"] is False
    assert seeded.key in [c["issue"]["key"] for c in body["candidates"]]
    assert seeded.key in _text(res) and "file_anyway" in _text(res)
    listed = (await rig["admin"].get("/issues", params={"project_id": rig["project"].id})).json()
    assert listed["total"] == 1  # nothing was filed

    filed = _result(await rig["mcp"].call("rw_file_bug", {**args, "file_anyway": True}))
    assert (await _get(rig["admin"], filed["key"]))["title"] == REACTION_DRAFT


async def test_a_refused_filing_keeps_its_uploads(factories, rig, search_jobs, fake_s3):
    await factories.issue(project_id=rig["project"].id, type="task", title=REACTION_SEEDED)
    await search_jobs.run()
    upload_id = await _upload(rig["mcp"], fake_s3)
    args = {"project": "chat", "title": REACTION_DRAFT, "upload_ids": [upload_id]}
    assert _error(await rig["mcp"].call("rw_file_bug", args)) == "duplicates_found"
    filed = _result(await rig["mcp"].call("rw_file_bug", {**args, "file_anyway": True}))
    assert [a["file_name"] for a in filed["attachments"]] == ["kibana-chat-errors-20261014.log"]


# ── Uploads (FR-M10, AC-M15, AC-M16) ─────────────────────────────────────────


async def test_upload_prepare_presigns_and_large_files_go_multipart(rig, fake_s3):
    small = _result(await rig["mcp"].call(
        "rw_upload_prepare", {"file_name": "screenshot-chat-20261015.png",
                              "mime_type": "image/png", "size": 2048},
    ))
    assert small["upload_id"].startswith("up_") and small["post"]["url"]
    assert "curl" in _text(await rig["mcp"].call(
        "rw_upload_prepare", {"file_name": "a.log", "mime_type": "text/plain", "size": 10},
    ))
    big = _result(await rig["mcp"].call(
        "rw_upload_prepare", {"file_name": "heap-dump-20261015.bin",
                              "mime_type": "application/octet-stream",
                              "size": 300 * 1024 * 1024},
    ))
    parts = big["multipart"]["parts"]
    assert "post" not in big and [p["part_number"] for p in parts] == [1, 2, 3, 4, 5]
    # The agent uploads every part; filing completes the upload and attaches it.
    key = parts[0]["url"].split("fake-s3.test/")[1].split("?")[0].replace("%2F", "/")
    fake_s3.put(key, b"x" * 1024, "application/octet-stream")
    filed = await _file_bug(rig, upload_ids=[big["upload_id"]])
    [att] = filed["attachments"]
    assert att["file_name"] == "heap-dump-20261015.bin" and att["size"] == 1024


async def test_ac_m15_two_uploads_become_two_agent_attachments(rig, fake_s3, background_jobs):
    mcp = rig["mcp"]
    log = await _upload(mcp, fake_s3)
    shot = await _upload(mcp, fake_s3, name="screenshot-reaction-missing-20261015.png",
                         mime="image/png", data=b"\x89PNG")
    filed = await _file_bug(rig, upload_ids=[log, shot])
    issue = await _get(rig["admin"], filed["key"])
    attachments = await _attachments(rig["admin"], issue["id"])
    assert sorted(a["file_name"] for a in attachments) == [
        "kibana-chat-errors-20261014.log", "screenshot-reaction-missing-20261015.png",
    ]
    assert all(a["via_agent"] and a["uploaded_by_id"] == rig["dev"].id for a in attachments)
    kinds = {a["file_name"]: a["attachment_type"] for a in attachments}
    assert kinds["screenshot-reaction-missing-20261015.png"] == "screenshot"
    assert kinds["kibana-chat-errors-20261014.log"] == "log"
    # The existing validation job runs for each, after the commit.
    assert len(background_jobs["validate_attachment"]) == 2


async def test_ac_m16_an_upload_of_another_user_or_used_twice_is_refused(
    factories, rig, fake_s3, mcp_client_for,
):
    other_mcp = await mcp_client_for(rig["qa"])
    theirs = await _upload(other_mcp, fake_s3)
    res = await rig["mcp"].call(
        "rw_file_bug", {"project": "chat", "title": BUG_TITLE, "upload_ids": [theirs]},
    )
    assert _error(res) == "unknown_upload"

    mine = await _upload(rig["mcp"], fake_s3)
    await _file_bug(rig, upload_ids=[mine])
    res = await rig["mcp"].call(
        "rw_file_tech_debt", {"project": "chat", "title": DEBT_TITLE, "upload_ids": [mine]},
    )
    assert _error(res) == "unknown_upload"
    bug = await _bug(factories, rig)
    assert _error(await rig["mcp"].call("rw_attach", {"key": bug.key, "upload_id": mine})) == (
        "unknown_upload"
    )
    listed = (await rig["admin"].get("/issues", params={"project_id": rig["project"].id})).json()
    assert listed["total"] == 2  # the first filing and the fixture bug only


async def test_an_upload_named_twice_or_never_uploaded_is_refused(rig, fake_s3):
    upload_id = await _upload(rig["mcp"], fake_s3)
    res = await rig["mcp"].call("rw_file_bug", {
        "project": "chat", "title": BUG_TITLE, "upload_ids": [upload_id, upload_id],
    })
    assert _error(res) == "unknown_upload"
    empty = _result(await rig["mcp"].call(
        "rw_upload_prepare", {"file_name": "x.log", "mime_type": "text/plain", "size": 5},
    ))
    res = await rig["mcp"].call("rw_file_bug", {
        "project": "chat", "title": BUG_TITLE, "upload_ids": [empty["upload_id"]],
    })
    assert _error(res) == "unknown_upload" and "no file yet" in res.structured_content["message"]


# ── Writing checks (BR-M19, AC-M17–M19) ──────────────────────────────────────


async def test_ac_m17_a_title_outside_15_to_90_characters_is_refused(rig):
    for title in ("x" * 120, "Too short"):
        res = await rig["mcp"].call("rw_file_bug", {"project": "chat", "title": title})
        assert _error(res) == "title_length", title
    assert _error(await rig["mcp"].call(
        "rw_file_tech_debt", {"project": "chat", "title": "y" * 91},
    )) == "title_length"
    await _file_bug(rig, title="z" * 90)


async def test_ac_m18_a_description_over_12000_characters_is_refused(rig):
    res = await rig["mcp"].call(
        "rw_file_bug", {"project": "chat", "title": BUG_TITLE, "description": "d" * 15_000},
    )
    assert _error(res) == "description_too_long"
    assert "Move logs, scripts, and long results to attachments." in res.structured_content[
        "message"
    ]
    await _file_bug(rig, description="d" * 12_000)


async def test_ac_m19_a_note_over_3000_characters_is_refused(factories, rig):
    bug = await _bug(factories, rig)
    res = await rig["mcp"].call("rw_add_note", {"key": bug.key, "body": "n" * 4_000})
    assert _error(res) == "note_too_long"
    _result(await rig["mcp"].call("rw_add_note", {"key": bug.key, "body": "n" * 3_000}))


# ── Existing items (FR-M16–M20, AC-M20–M26) ──────────────────────────────────


@pytest.fixture
async def support_bug(factories, rig):
    template = await factories.support_template(project_id=rig["project"].id)
    report = await factories.support_report(rig["support_client"], template=template)
    return report


async def test_ac_m20_an_agent_note_is_internal_and_support_never_sees_it(rig, support_bug):
    key = f"BUG-{support_bug.issue_number}"
    note = _result(await rig["mcp"].call(
        "rw_add_note", {"key": key, "body": "Fixed in https://git/pr/7"},
    ))
    assert note["internal"] is True and note["via_agent"] is True
    tech = [e for e in await _timeline(rig["admin"], support_bug.id) if e["event_type"] == "comment"]
    assert [(e["body"], e["is_internal"], e["via_agent"]) for e in tech] == [
        ("Fixed in https://git/pr/7", True, True),
    ]
    seen_by_support = await _timeline(rig["support_client"], support_bug.id)
    assert not any(e["event_type"] == "comment" for e in seen_by_support)


async def test_ac_m21_support_sees_an_agent_attachment_on_their_report(
    rig, support_bug, fake_s3,
):
    key = f"BUG-{support_bug.issue_number}"
    upload_id = await _upload(rig["mcp"], fake_s3, name="screenshot-x-20261015.png",
                              mime="image/png", data=b"\x89PNG")
    attached = _result(await rig["mcp"].call("rw_attach", {"key": key, "upload_id": upload_id}))
    assert attached["attachment"]["via_agent"] is True
    [att] = await _attachments(rig["support_client"], support_bug.id)
    assert att["file_name"] == "screenshot-x-20261015.png" and att["via_agent"] is True


async def test_ac_m22_the_agent_fills_empty_reproduction_steps(factories, rig):
    bug = await _bug(factories, rig)
    res = await rig["mcp"].call("rw_fill_field", {
        "key": bug.key, "field": "reproduction_steps",
        "value": [{"description": "Open a group chat"},
                  {"description": "React", "expected_result": "Kept", "actual_result": "Lost"}],
    })
    assert _result(res)["filled"] == ["reproduction_steps"]
    issue = await _get(rig["admin"], bug.id)
    assert [s["description"] for s in issue["reproduction_steps"]] == ["Open a group chat", "React"]
    [fill] = [e for e in await _timeline(rig["admin"], bug.id) if e["event_type"] == "steps_changed"]
    assert fill["via_agent"] is True and fill["actor_id"] == rig["dev"].id


async def test_ac_m23_a_field_with_a_value_is_never_filled(factories, rig):
    bug = await _bug(
        factories, rig, curl_command="curl https://x", environment_browser="Safari 18",
        reproduction_steps=[{"step_order": 1, "description": "Open"}],
    )
    mcp = rig["mcp"]
    for field, value in (
        ("curl", "curl https://y"),
        ("reproduction_steps", [{"description": "Other"}]),
        ("environment", {"browser": "Firefox", "os": "Linux"}),
    ):
        res = await mcp.call("rw_fill_field", {"key": bug.key, "field": field, "value": value})
        assert _error(res) == "field_not_empty", field
    # Empty sub-fields of the environment can still be filled.
    _result(await mcp.call(
        "rw_fill_field", {"key": bug.key, "field": "environment", "value": {"os": "Linux"}},
    ))
    issue = await _get(rig["admin"], bug.id)
    assert issue["curl_command"] == "curl https://x"
    assert issue["environment_browser"] == "Safari 18" and issue["environment_os"] == "Linux"


async def test_fill_field_takes_bugs_only_and_a_matching_value(factories, rig):
    task = await factories.issue(project_id=rig["project"].id, type="task")
    res = await rig["mcp"].call("rw_fill_field", {"key": task.key, "field": "curl", "value": "c"})
    assert _error(res) == "bug_only"
    bug = await _bug(factories, rig)
    res = await rig["mcp"].call(
        "rw_fill_field", {"key": bug.key, "field": "curl", "value": {"browser": "x"}},
    )
    assert _error(res) == "invalid_value"


async def test_ac_m24_a_done_bug_takes_no_fill_and_no_recurrence(factories, rig):
    bug = await _bug(factories, rig, "in_progress", "in_review", "done")
    mcp = rig["mcp"]
    res = await mcp.call("rw_fill_field", {"key": bug.key, "field": "curl", "value": "curl z"})
    assert _error(res) == "item_closed"
    res = await mcp.call("rw_report_recurrence", {"key": bug.key, "comment": "Again."})
    assert _error(res) == "recurrence_not_allowed"
    cancelled = await _bug(factories, rig, "cancelled")
    res = await mcp.call("rw_fill_field", {"key": cancelled.key, "field": "curl", "value": "c"})
    assert _error(res) == "item_closed"
    assert (await _get(rig["admin"], bug.id))["recurrence_count"] == 1


async def test_ac_m25_a_recurrence_counts_and_carries_the_badge(factories, rig):
    bug = await _bug(factories, rig)
    resp = await rig["qa_client"].post(
        f"/issues/{bug.id}/recurrences", json={"comment": "A customer saw it."},
    )
    assert resp.status_code in (200, 201), resp.text
    assert (await _get(rig["admin"], bug.id))["recurrence_count"] == 2

    res = _result(await rig["mcp"].call(
        "rw_report_recurrence", {"key": bug.key, "comment": "Seen again in the logs."},
    ))
    assert res["recurrence_count"] == 3
    recurrences = [
        e for e in await _timeline(rig["admin"], bug.id) if e["event_type"] == "recurrence"
    ]
    assert [e["via_agent"] for e in recurrences] == [False, True]
    # Same effects as the web app: the assignee hears about it.
    assert "comment" in await _inbox_types(rig["qa_client"])


async def test_a_recurrence_on_a_cancelled_bug_is_allowed(factories, rig):
    bug = await _bug(factories, rig, "cancelled")
    res = _result(await rig["mcp"].call(
        "rw_report_recurrence", {"key": bug.key, "comment": "Back again."},
    ))
    assert res["status"] == "cancelled" and res["recurrence_count"] == 2


async def test_ac_m26_no_tool_changes_the_description_of_an_existing_item(factories, rig):
    for tool in await rig["mcp"].tools():
        props = tool.input_schema.get("properties", {})
        if "key" in props:
            assert "description" not in props and "title" not in props, tool.name
    bug = await _bug(factories, rig, description="Written by a person.")
    res = await rig["mcp"].call(
        "rw_fill_field", {"key": bug.key, "field": "description", "value": "Rewritten."},
    )
    assert res.is_error
    assert (await _get(rig["admin"], bug.id))["description"] == "Written by a person."


# ── Origin filter (FR-M30, AC-M35) ───────────────────────────────────────────


async def test_ac_m35_backlog_triage_and_tech_debt_filter_by_origin(factories, rig):
    agent_debt = _result(await rig["mcp"].call(
        "rw_file_tech_debt", {"project": "chat", "title": DEBT_TITLE},
    ))
    agent_bug = await _file_bug(rig)
    person_debt = await factories.issue(
        project_id=rig["project"].id, type="task", is_tech_debt=True,
    )
    person_task = await factories.issue(project_id=rig["project"].id, type="task")
    person_bug = await factories.issue(project_id=rig["project"].id)
    admin, pid = rig["admin"], rig["project"].id

    async def keys(path, **params):
        resp = await admin.get(path, params=params)
        assert resp.status_code == 200, resp.text
        return {i["key"] for i in resp.json()["items"]}

    backlog = f"/projects/{pid}/backlog"
    assert await keys(backlog, include_tech_debt=True, origin="agent") == {agent_debt["key"]}
    assert await keys(backlog, include_tech_debt=True, origin="people") == {
        person_debt.key, person_task.key,
    }
    assert await keys(backlog, include_tech_debt=True) == {
        agent_debt["key"], person_debt.key, person_task.key,
    }
    triage = {"project_id": pid, "statuses": "new,needs_info"}
    assert await keys("/issues", **triage, origin="agent") == {agent_bug["key"]}
    assert await keys("/issues", **triage, origin="people") == {person_bug.key}
    assert await keys("/tech-debt", origin="agent") == {agent_debt["key"]}
    assert await keys("/tech-debt", origin="people") == {person_debt.key}
    assert (await admin.get("/tech-debt", params={"origin": "bots"})).status_code == 422


async def test_read_tools_report_via_agent(rig):
    filed = await _file_bug(rig)
    debt = _result(await rig["mcp"].call(
        "rw_file_tech_debt", {"project": "chat", "title": DEBT_TITLE},
    ))
    item = _result(await rig["mcp"].call("rw_get_item", {"key": filed["key"]}))
    assert item["via_agent"] is True
    assert all(e["via_agent"] for e in item["timeline"])
    [row] = _result(await rig["mcp"].call("rw_triage_queue", {"project": "chat"}))["items"]
    assert row["key"] == filed["key"] and row["via_agent"] is True
    [debt_row] = _result(await rig["mcp"].call("rw_tech_debt", {}))["items"]
    assert debt_row["key"] == debt["key"] and debt_row["via_agent"] is True


async def test_the_card_hover_carries_the_badge(rig):
    filed = _result(await rig["mcp"].call(
        "rw_file_tech_debt", {"project": "chat", "title": DEBT_TITLE, "assignee": "dana"},
    ))
    groups = (await rig["dev_client"].get(f"/users/{rig['dev'].id}/queue")).json()["groups"]
    [entry] = groups["rest"]
    assert entry["issue"]["key"] == filed["key"] and entry["issue"]["via_agent"] is True


# ── cURL and environment on the timeline (A.5) ───────────────────────────────


async def test_curl_and_environment_changes_leave_timeline_events(factories, rig):
    bug = await _bug(factories, rig, environment_name="staging")
    dev = rig["dev_client"]
    types_before = await _inbox_types(rig["qa_client"])

    resp = await dev.patch(f"/issues/{bug.id}", json={"curl_command": "curl https://a"})
    assert resp.status_code == 200, resp.text
    resp = await dev.patch(f"/issues/{bug.id}", json={"environment_browser": "Edge 130"})
    assert resp.status_code == 200, resp.text
    events = await _timeline(rig["admin"], bug.id)
    [curl] = [e for e in events if e["event_type"] == "curl_changed"]
    assert curl["meta"] in ({}, None)
    [env] = [e for e in events if e["event_type"] == "environment_changed"]
    assert env["meta"]["fields"] == ["environment_browser"]
    assert env["meta"]["changes"]["environment_browser"] == {"from": None, "to": "Edge 130"}
    # A browser change sends no notice.
    assert (await _inbox_types(rig["qa_client"])).count("environment_changed") == (
        types_before.count("environment_changed")
    )

    resp = await dev.patch(f"/issues/{bug.id}", json={"environment_name": "production"})
    assert resp.status_code == 200, resp.text
    assert (await _inbox_types(rig["qa_client"])).count("environment_changed") == (
        types_before.count("environment_changed") + 1
    )

    # Sending a field unchanged (or "" for an empty one) records nothing.
    resp = await dev.patch(f"/issues/{bug.id}", json={
        "environment_browser": "Edge 130", "environment_os": "", "curl_command": "curl https://a",
    })
    assert resp.status_code == 200, resp.text
    after = await _timeline(rig["admin"], bug.id)
    assert len([e for e in after if e["event_type"] in ("environment_changed", "curl_changed")]) == 3
