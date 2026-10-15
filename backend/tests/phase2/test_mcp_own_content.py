"""Slice 18 — own content, prompts, and the writing standard.

docs/phase-2/18-mcp-own-content-and-prompts.md (prd-mcp.md FR-M03 ``you_can_edit``,
FR-M25–FR-M28, FR-M31, FR-M33–FR-M37, BR-M07, BR-M14, BR-M18, AC-M27–AC-M33).
Tools are driven through ``/mcp`` with the in-process MCP client; people's
changes go through ``/api/v1``. The last-writer rule itself is the unit table in
``test_agent_ownership.py``; this file checks the tools apply it.
"""

from pathlib import Path

import pytest

from app.mcp_server import prompts as prompt_content
from tests.phase2.test_mcp_read_tools import _error, _result, _text
from tests.phase2.test_mcp_write_tools import (
    BUG_TITLE,
    DEBT_TITLE,
    _attachments,
    _get,
    _timeline,
    _upload,
)

NEW_TITLE = "Chat reactions vanish after a refresh in group chats"
STANDARD_PATH = Path(prompt_content.__file__).parent / "content" / "agent-writing-standard.md"


# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def rig(factories, client_for, mcp_client_for, mcp_token):
    dev = await factories.user(role="developer", name="Dana Dev", username="dana")
    other = await factories.user(role="developer", name="Omar Other", username="omar")
    lead = await factories.user(role="qa", name="Tara Triage")
    project = await factories.project(name="Chat", slug="chat", triage_lead_id=lead.id)
    token_a = await mcp_token(dev, name="Claude Code — laptop")
    return {
        "admin": factories.admin_client,
        "dev": dev, "dev_client": await client_for(dev),
        "other": other, "other_mcp": await mcp_client_for(other),
        "project": project,
        "stream_id": await factories.stream_id(project_id=project.id),
        "token_a": token_a,
        "mcp": await mcp_client_for(dev, token_a),
    }


async def _file_bug(rig, mcp=None, **args) -> dict:
    return _result(await (mcp or rig["mcp"]).call(
        "rw_file_bug", {"project": "chat", "title": BUG_TITLE, **args},
    ))


async def _note(rig, key, body="The worker drops the event.", mcp=None) -> int:
    return _result(await (mcp or rig["mcp"]).call(
        "rw_add_note", {"key": key, "body": body},
    ))["note_id"]


async def _update(mcp, key, target, value):
    return await mcp.call("rw_update_own", {"key": key, "target": target, "value": value})


async def _delete(mcp, key, target):
    return await mcp.call("rw_delete_own", {"key": key, "target": target})


async def _item(mcp, key) -> dict:
    return _result(await mcp.call("rw_get_item", {"key": key, "full_timeline": True}))


def _entry(item: dict, event_id: int) -> dict:
    return next(e for e in item["timeline"] if e["id"] == event_id)


async def _person_attachment(client, issue_id, fake_s3) -> int:
    fake_s3.put("attachments/person.png", b"\x89PNG", "image/png")
    resp = await client.post(f"/issues/{issue_id}/attachments/confirm", json={
        "s3_key": "attachments/person.png", "filename": "screenshot-person-20261015.png",
        "mime_type": "image/png", "file_size_bytes": 4, "attachment_type": "screenshot",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


# ── Notes (AC-M27, AC-M28, AC-M29) ───────────────────────────────────────────


async def test_ac_m27_an_agent_edit_of_its_note_shows_the_edited_marker(rig):
    filed = await _file_bug(rig)
    note_id = await _note(rig, filed["key"])

    data = _result(await _update(rig["mcp"], filed["key"], f"note:{note_id}", "The API drops it."))
    assert data == {"key": filed["key"], "target": f"note:{note_id}", "edited": True}

    issue = await _get(rig["admin"], filed["key"])
    [note] = [e for e in await _timeline(rig["dev_client"], issue["id"]) if e["id"] == note_id]
    assert note["body"] == "The API drops it."
    assert note["edited_at"] is not None  # the same marker a person's edit shows
    assert note["via_agent"] is True
    # The agent is still the last writer, so it can correct the note again.
    _result(await _update(rig["mcp"], filed["key"], f"note:{note_id}", "The worker drops it."))


async def test_ac_m28_after_a_ui_edit_the_agent_cannot_edit_or_delete_the_note(rig):
    filed = await _file_bug(rig)
    note_id = await _note(rig, filed["key"])
    issue = await _get(rig["admin"], filed["key"])

    resp = await rig["dev_client"].patch(
        f"/issues/{issue['id']}/timeline/{note_id}", json={"body": "Corrected by Dana."},
    )
    assert resp.status_code == 200, resp.text

    res = await _update(rig["mcp"], filed["key"], f"note:{note_id}", "Agent again.")
    assert _error(res) == "not_owner"
    assert _error(await _delete(rig["mcp"], filed["key"], f"note:{note_id}")) == "not_owner"
    assert not _entry(await _item(rig["mcp"], filed["key"]), note_id)["you_can_edit"]

    # In the UI the note is still the owner's own (FR-M28).
    resp = await rig["dev_client"].delete(f"/issues/{issue['id']}/timeline/{note_id}")
    assert resp.status_code == 204, resp.text


async def test_ac_m29_another_users_agent_cannot_edit_or_delete_the_note(rig):
    filed = await _file_bug(rig)
    note_id = await _note(rig, filed["key"])
    other = rig["other_mcp"]

    assert _error(await _update(other, filed["key"], f"note:{note_id}", "Mine now.")) == "not_owner"
    assert _error(await _delete(other, filed["key"], f"note:{note_id}")) == "not_owner"
    for piece in ("title", "description"):
        assert _error(await _update(other, filed["key"], piece, NEW_TITLE)) == "not_owner"
    assert not _entry(await _item(other, filed["key"]), note_id)["you_can_edit"]


async def test_the_agent_deletes_its_own_note(rig):
    filed = await _file_bug(rig)
    note_id = await _note(rig, filed["key"])

    data = _result(await _delete(rig["mcp"], filed["key"], f"note:{note_id}"))
    assert data == {"key": filed["key"], "target": f"note:{note_id}", "deleted": True}
    issue = await _get(rig["admin"], filed["key"])
    assert note_id not in [e["id"] for e in await _timeline(rig["admin"], issue["id"])]
    assert _error(await _delete(rig["mcp"], filed["key"], f"note:{note_id}")) == "note_not_found"


async def test_a_note_a_person_wrote_is_not_the_agents(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, client=rig["dev_client"])
    resp = await rig["dev_client"].post(
        f"/issues/{bug.id}/timeline", json={"body": "Typed in the UI.", "is_internal": True},
    )
    note_id = resp.json()["id"]
    assert _error(await _update(rig["mcp"], bug.key, f"note:{note_id}", "x")) == "not_owner"


# ── Title and description (AC-M30, AC-M31, BR-M14) ───────────────────────────


async def test_ac_m30_title_editable_while_new_and_final_after_triage_accepts(rig):
    filed = await _file_bug(rig)
    key = filed["key"]
    assert _result(await _update(rig["mcp"], key, "title", NEW_TITLE))["edited"]
    _result(await _update(rig["mcp"], key, "description", "## Summary\nReactions vanish."))
    issue = await _get(rig["admin"], key)
    assert issue["title"] == NEW_TITLE
    assert issue["description"] == "## Summary\nReactions vanish."
    # The agent's own title_changed keeps it the last writer.
    item = await _item(rig["mcp"], key)
    assert item["you_can_edit"]["title"] and item["you_can_edit"]["description"]

    resp = await rig["admin"].post(f"/issues/{issue['id']}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": rig["stream_id"],
    })
    assert resp.status_code == 200, resp.text

    assert _error(await _update(rig["mcp"], key, "title", BUG_TITLE)) == "item_triaged"
    assert _error(await _update(rig["mcp"], key, "description", "x")) == "item_triaged"
    item = await _item(rig["mcp"], key)
    assert not item["you_can_edit"]["title"] and not item["you_can_edit"]["description"]
    assert (await _get(rig["admin"], key))["title"] == NEW_TITLE


async def test_ac_m31_tech_debt_text_is_final_once_a_pm_places_it_in_the_stream(
    factories, client_for, rig,
):
    filed = _result(await rig["mcp"].call(
        "rw_file_tech_debt", {"project": "chat", "title": DEBT_TITLE},
    ))
    key = filed["key"]
    _result(await _update(rig["mcp"], key, "description", "## Summary\nRetries never stop."))
    assert (await _item(rig["mcp"], key))["you_can_edit"]["fields"] == {}  # tasks have none

    pm = await client_for(await factories.user(role="product_manager"))
    issue = await _get(rig["admin"], key)
    resp = await pm.patch(f"/issues/{issue['id']}", json={"release_id": rig["stream_id"]})
    assert resp.status_code == 200, resp.text

    assert _error(await _update(rig["mcp"], key, "title", NEW_TITLE)) == "item_triaged"
    assert _error(await _update(rig["mcp"], key, "description", "x")) == "item_triaged"
    assert not (await _item(rig["mcp"], key))["you_can_edit"]["title"]


async def test_a_title_a_person_changed_or_an_item_a_person_filed_is_not_the_agents(
    factories, rig,
):
    filed = await _file_bug(rig)
    issue = await _get(rig["admin"], filed["key"])
    resp = await rig["dev_client"].patch(f"/issues/{issue['id']}", json={"title": NEW_TITLE})
    assert resp.status_code == 200, resp.text
    assert _error(await _update(rig["mcp"], filed["key"], "title", BUG_TITLE)) == "not_owner"
    # The description is a separate piece: still the agent's.
    _result(await _update(rig["mcp"], filed["key"], "description", "## Summary\nStill mine."))

    human = await factories.issue(project_id=rig["project"].id, client=rig["dev_client"])
    assert _error(await _update(rig["mcp"], human.key, "title", NEW_TITLE)) == "not_owner"


async def test_the_writing_checks_apply_to_edits(rig):
    filed = await _file_bug(rig)
    note_id = await _note(rig, filed["key"])
    key = filed["key"]
    assert _error(await _update(rig["mcp"], key, "title", "Too short")) == "title_length"
    assert _error(await _update(rig["mcp"], key, "description", "x" * 12_001)) == (
        "description_too_long"
    )
    assert _error(await _update(rig["mcp"], key, f"note:{note_id}", "x" * 3_001)) == (
        "note_too_long"
    )
    assert (await _get(rig["admin"], key))["title"] == BUG_TITLE


async def test_an_unknown_target_is_refused(rig):
    filed = await _file_bug(rig)
    for target in ("status", "field:labels", "note:abc", "attachment:1"):
        assert _error(await _update(rig["mcp"], filed["key"], target, "x")) == "invalid_target"
    assert _error(await _delete(rig["mcp"], filed["key"], "title")) == "invalid_target"


# ── Fields (AC-M33) ──────────────────────────────────────────────────────────


async def test_ac_m33_a_curl_changed_in_the_ui_is_no_longer_the_agents(factories, rig):
    bug = await factories.issue(project_id=rig["project"].id, client=rig["dev_client"])
    _result(await rig["mcp"].call(
        "rw_fill_field", {"key": bug.key, "field": "curl", "value": "curl https://a"},
    ))
    _result(await _update(rig["mcp"], bug.key, "field:curl", "curl https://b"))
    assert (await _get(rig["admin"], bug.id))["curl_command"] == "curl https://b"

    resp = await rig["dev_client"].patch(f"/issues/{bug.id}", json={"curl_command": "curl c"})
    assert resp.status_code == 200, resp.text

    assert _error(await _update(rig["mcp"], bug.key, "field:curl", "curl d")) == "not_owner"
    assert (await _item(rig["mcp"], bug.key))["you_can_edit"]["fields"]["curl"] is False
    assert (await _get(rig["admin"], bug.id))["curl_command"] == "curl c"


async def test_fields_are_final_once_the_bug_is_done_or_cancelled(rig):
    filed = await _file_bug(rig, curl="curl https://a", reproduction_steps=[
        {"description": "Open the group chat."},
    ])
    key = filed["key"]
    _result(await _update(rig["mcp"], key, "field:reproduction_steps", [
        {"description": "Open the group chat.", "actual_result": "No reaction."},
    ]))
    _result(await _update(rig["mcp"], key, "field:environment", {"browser": "Firefox 131"}))
    issue = await _get(rig["admin"], key)
    assert issue["reproduction_steps"][0]["actual_result"] == "No reaction."
    assert issue["environment_browser"] == "Firefox 131"

    resp = await rig["admin"].post(f"/issues/{issue['id']}/transition", json={"to": "cancelled"})
    assert resp.status_code == 200, resp.text
    assert _error(await _update(rig["mcp"], key, "field:curl", "curl b")) == "item_closed"
    assert (await _item(rig["mcp"], key))["you_can_edit"]["fields"] == {
        "reproduction_steps": False, "curl": False, "environment": False,
    }


# ── Attachments ──────────────────────────────────────────────────────────────


async def test_the_agent_deletes_its_own_attachment_but_not_a_persons(factories, rig, fake_s3):
    upload_id = await _upload(rig["mcp"], fake_s3)
    filed = await _file_bug(rig, upload_ids=[upload_id])
    [mine] = filed["attachments"]
    issue = await _get(rig["admin"], filed["key"])
    theirs = await _person_attachment(rig["dev_client"], issue["id"], fake_s3)

    item = await _item(rig["mcp"], filed["key"])
    flags = {a["id"]: a["you_can_edit"] for a in item["attachments"]}
    assert flags == {mine["id"]: True, theirs: False}

    assert _error(await _delete(rig["mcp"], filed["key"], f"attachment:{theirs}")) == "not_owner"
    _result(await _delete(rig["mcp"], filed["key"], f"attachment:{mine['id']}"))
    assert [a["id"] for a in await _attachments(rig["admin"], issue["id"])] == [theirs]
    assert not any(k.endswith("kibana-chat-errors-20261014.log") for k in fake_s3.objects)
    assert _error(await _delete(rig["other_mcp"], filed["key"], f"attachment:{theirs}")) == (
        "not_owner"
    )


# ── Two tokens (AC-M32) ──────────────────────────────────────────────────────


async def test_ac_m32_content_made_with_token_a_is_editable_with_token_b(
    rig, mcp_token, mcp_client_for, fake_s3,
):
    upload_id = await _upload(rig["mcp"], fake_s3)
    filed = await _file_bug(rig, upload_ids=[upload_id])
    note_id = await _note(rig, filed["key"])

    token_b = await mcp_token(rig["dev"], name="Cursor — desktop")
    resp = await rig["dev_client"].post(f"/me/mcp/tokens/{rig['token_a'].id}/revoke")
    assert resp.status_code == 200, resp.text  # active or not, token A is still the user's
    with_b = await mcp_client_for(rig["dev"], token_b)

    _result(await _update(with_b, filed["key"], "title", NEW_TITLE))
    _result(await _update(with_b, filed["key"], f"note:{note_id}", "Edited with token B."))
    _result(await _delete(with_b, filed["key"], f"attachment:{filed['attachments'][0]['id']}"))


# ── you_can_edit (FR-M03) ────────────────────────────────────────────────────


async def test_you_can_edit_matches_the_tool_outcomes(rig, fake_s3):
    """For every piece, an edit attempt succeeds exactly when the flag is true."""
    filed = await _file_bug(rig, curl="curl https://a")
    key = filed["key"]
    issue = await _get(rig["admin"], key)
    agent_note = await _note(rig, key)
    resp = await rig["dev_client"].post(
        f"/issues/{issue['id']}/timeline", json={"body": "A person's note.", "is_internal": True},
    )
    person_note = resp.json()["id"]
    resp = await rig["dev_client"].patch(f"/issues/{issue['id']}", json={
        "reproduction_steps": [{"step_order": 1, "description": "Open the chat."}],
    })
    assert resp.status_code == 200, resp.text
    theirs = await _person_attachment(rig["dev_client"], issue["id"], fake_s3)
    mine = (await _attachments(rig["admin"], issue["id"]))  # none yet from the agent
    assert [a["id"] for a in mine] == [theirs]
    upload_id = await _upload(rig["mcp"], fake_s3)
    mine = _result(await rig["mcp"].call(
        "rw_attach", {"key": key, "upload_id": upload_id},
    ))["attachment"]["id"]

    values = {
        "title": NEW_TITLE,
        "description": "## Summary\nReactions vanish.",
        "field:reproduction_steps": [{"description": "Open the group chat."}],
        "field:curl": "curl https://b",
        "field:environment": {"browser": "Firefox 131"},
        f"note:{agent_note}": "Corrected.",
        f"note:{person_note}": "Not mine.",
    }

    async def check() -> None:
        item = await _item(rig["mcp"], key)
        can = item["you_can_edit"]
        flags = {
            "title": can["title"],
            "description": can["description"],
            **{f"field:{name}": ok for name, ok in can["fields"].items()},
            f"note:{agent_note}": _entry(item, agent_note)["you_can_edit"],
            f"note:{person_note}": _entry(item, person_note)["you_can_edit"],
        }
        assert set(flags) == set(values)
        for target, flag in flags.items():
            res = await _update(rig["mcp"], key, target, values[target])
            assert res.is_error is not flag, (target, flag, _text(res))

    await check()  # New: the agent owns the text, curl, environment, its note
    resp = await rig["admin"].post(f"/issues/{issue['id']}/triage", json={
        "outcome": "accept", "priority": "high", "release_id": rig["stream_id"],
    })
    assert resp.status_code == 200, resp.text
    await check()  # accepted: the title and description are final

    item = await _item(rig["mcp"], key)
    for a in item["attachments"]:
        res = await _delete(rig["mcp"], key, f"attachment:{a['id']}")
        assert res.is_error is not a["you_can_edit"], a
    assert {a["id"] for a in item["attachments"]} == {mine, theirs}


async def test_the_item_resource_and_markdown_say_what_the_agent_can_edit(rig):
    filed = await _file_bug(rig)
    note_id = await _note(rig, filed["key"])
    text = (await rig["mcp"].call(f"rw://item/{filed['key']}")).contents[0].text
    assert "**You can edit (rw_update_own):** title, description" in text
    assert f"internal note {note_id} · you can edit" in text


# ── Prompts (FR-M33–FR-M35, FR-M37) ──────────────────────────────────────────

BOUNDARY_LINES = (
    "Never change the status, the container, or the placement of an item.",
    "Ask the developer before you set an assignee or a priority, before you report a "
    "recurrence, and before you file with `file_anyway=true`.",
    "Write English in ASD-STE100",
)


async def test_the_server_offers_three_prompts(rig):
    prompts = {p.name: p for p in await rig["mcp"].prompts()}
    assert set(prompts) == {"rw-next", "rw-work", "rw-report"}
    assert not prompts["rw-next"].arguments
    assert not prompts["rw-report"].arguments
    [arg] = prompts["rw-work"].arguments
    assert arg.name == "key" and arg.required


def _prompt_text(result) -> str:
    return "\n".join(m.content.text for m in result.messages if m.content.type == "text")


def _embedded(result) -> list:
    return [m.content.resource for m in result.messages if m.content.type == "resource"]


@pytest.mark.parametrize(("name", "args", "tools"), [
    ("rw-next", {}, ("rw_my_queue", "rw_get_item", "rw_get_attachment", "rw_add_note")),
    ("rw-work", {"key": "bug-42"}, ("rw_get_item", "rw_get_attachment", "rw_add_note")),
    ("rw-report", {}, (
        "rw_tech_debt", "rw_upload_prepare", "rw_file_bug", "rw_file_tech_debt", "rw_get_item",
        "rw_add_note", "rw_attach", "rw_fill_field", "rw_report_recurrence",
    )),
])
async def test_each_prompt_names_its_tools_and_states_the_boundaries(rig, name, args, tools):
    result = await rig["mcp"].prompt(name, args)
    text = _prompt_text(result)
    for tool in tools:
        assert f"`{tool}`" in text, tool
    for line in BOUNDARY_LINES:
        assert line in text
    if name == "rw-next":
        assert "move the status" in text and "rejected" in text
    if name == "rw-work":
        assert "BUG-42" in text and "{key}" not in text
        assert "PR: [<PR title>](<url>)" in text
    if name == "rw-report":
        assert "duplicates_found" in text and "Do not set `file_anyway`" in text
        assert "propose a priority" in text


@pytest.mark.parametrize(("name", "args"), [("rw-work", {"key": "BUG-1"}), ("rw-report", {})])
async def test_the_writing_prompts_embed_the_standard(rig, name, args):
    [standard] = _embedded(await rig["mcp"].prompt(name, args))
    assert str(standard.uri) == "rw://standards/writing"
    assert standard.text == STANDARD_PATH.read_text(encoding="utf-8").strip()


# ── The writing standard (FR-M36, FR-M31) ────────────────────────────────────


async def test_the_standard_resource_returns_the_file(rig):
    result = await rig["mcp"].call("rw://standards/writing")
    [content] = result.contents
    assert content.text == STANDARD_PATH.read_text(encoding="utf-8").strip()
    assert content.text.startswith("# Releasewatch — Agent Writing Standard")
    assert "ASD-STE100" in content.text


WRITE_TOOLS = (
    "rw_upload_prepare", "rw_file_bug", "rw_file_tech_debt", "rw_add_note", "rw_attach",
    "rw_fill_field", "rw_report_recurrence", "rw_update_own", "rw_delete_own",
)


async def test_write_tool_descriptions_carry_the_standard_briefly(rig):
    tools = {t.name: t.description for t in await rig["mcp"].tools()}
    for name in WRITE_TOOLS:
        assert len(tools[name]) <= 1_500, name
    for name in ("rw_file_bug", "rw_file_tech_debt", "rw_add_note", "rw_report_recurrence",
                 "rw_update_own", "rw_fill_field"):
        assert "ASD-STE100" in tools[name] and "rw://standards/writing" in tools[name], name
    for name in ("rw_file_bug", "rw_file_tech_debt"):
        assert "Source | Locator | Time range" in tools[name]
        assert "file_anyway=true only" in tools[name]
        assert "Show the developer the draft first" in tools[name]
    assert "Summary, Observed behavior, Expected behavior, Evidence" in tools["rw_file_bug"]
    assert "Current state, Evidence, Risk, Suggested approach" in tools["rw_file_tech_debt"]


async def test_the_guidance_says_one_action_per_reproduction_step(rig):
    """BUG-918: an agent wrote the environment, the user and the call as one step."""
    tools = {t.name: t for t in await rig["mcp"].tools()}
    for name in ("rw_file_bug", "rw_fill_field"):
        assert "one action per step" in tools[name].description.lower(), name
        assert "the environment" in tools[name].description and "step" in tools[name].description
    schema = tools["rw_file_bug"].input_schema
    step = schema["$defs"]["StepInput"]["properties"]["description"]["description"]
    assert "One action" in step and "precondition is its own step" in step
    standard = STANDARD_PATH.read_text(encoding="utf-8")
    assert "Write one action in one step." in standard
    assert "Put each precondition in its own step" in standard
    report = _prompt_text(await rig["mcp"].prompt("rw-report"))
    assert "Write one action in each step" in report
