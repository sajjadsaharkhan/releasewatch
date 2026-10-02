"""Slice 13 — Jev integration (engine PRD FR-S03, FR-S16, FR-S18; BR-S01–S03, S05, S14, S18).

Jev is the fake from ``tests/fakes/jev.py`` (autouse ``jev`` fixture); embeddings
are the fake endpoint, index jobs run through ``search_jobs``. Jev is switched
on the way an Admin does it: save a key, Test connection, Enabled.
"""

import pytest

from app.search.jev import JOB_RETRIES

KEY = "tsk-test-0123456789abcdef"
REACTION = "ری‌اکشن روی پیام‌های گروه ذخیره نمی‌شود"
REACTION_PRIVATE = "شمارنده ری‌اکشن در چت خصوصی اشتباه است"
REACTION_EDIT = "ری‌اکشن بعد از ویرایش پیام گروه حذف می‌شود"


async def enable_jev(admin, key: str = KEY) -> None:
    assert (await admin.put("/settings/search/jev", json={"api_key": key})).status_code == 200
    test = await admin.post("/settings/search/jev/test")
    assert test.status_code == 200 and test.json()["ok"], test.text
    resp = await admin.put("/settings/search/jev", json={"enabled": True})
    assert resp.status_code == 200, resp.text


async def _search(client, q, **params):
    resp = await client.get("/search", params={"q": q, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ids(rows):
    return [r["issue_id"] for r in rows]


def _rerank_ids(call) -> list[int]:
    return [int(k.removeprefix("c_")) for k in call["questions"]]


@pytest.fixture
async def project(factories):
    return await factories.project()


@pytest.fixture
async def reactions(factories, project, search_jobs):
    """Three items about reactions, indexed — all found by stage 1 for ``ری‌اکشن``."""
    items = {
        "group": await factories.issue(project_id=project.id, title=REACTION),
        "private": await factories.issue(project_id=project.id, title=REACTION_PRIVATE),
        "edit": await factories.issue(project_id=project.id, title=REACTION_EDIT),
    }
    await search_jobs.run()
    return items


# ── Settings (FR-S18, AC-S19, AC-S20, BR-S18) ────────────────────────────────


async def test_ac_s19_cannot_enable_without_successful_test(factories, jev):
    admin = factories.admin_client
    resp = await admin.put("/settings/search/jev", json={"enabled": True})
    assert resp.status_code == 409 and resp.json()["code"] == "jev_test_required"

    assert (await admin.put("/settings/search/jev", json={"api_key": KEY})).status_code == 200
    resp = await admin.put("/settings/search/jev", json={"enabled": True})
    assert resp.status_code == 409 and resp.json()["code"] == "jev_test_required"

    jev.fail("http_401")
    test = (await admin.post("/settings/search/jev/test")).json()
    assert test["ok"] is False and test["reason"] == "http_401"
    assert (await admin.put("/settings/search/jev", json={"enabled": True})).status_code == 409

    jev.fail(None)
    test = (await admin.post("/settings/search/jev/test")).json()
    assert test["ok"] is True and test["model"] == "jev-1.13.0" and test["latency_ms"] >= 0
    assert jev.auth[-1] == f"Bearer {KEY}"
    resp = await admin.put("/settings/search/jev", json={"enabled": True})
    assert resp.status_code == 200 and resp.json()["enabled"] is True
    assert (await admin.get("/features")).json() == {"jev_enabled": True}


async def test_saving_a_new_key_disables_jev_and_needs_a_new_test(factories, jev):
    admin = factories.admin_client
    await enable_jev(admin)
    body = (
        await admin.put("/settings/search/jev", json={"api_key": "tsk-another-key-9999"})
    ).json()
    assert body["enabled"] is False and body["can_enable"] is False and body["key_last4"] == "9999"
    assert (await admin.get("/features")).json() == {"jev_enabled": False}
    resp = await admin.put("/settings/search/jev", json={"enabled": True})
    assert resp.status_code == 409


async def test_ac_s20_api_never_returns_key(factories, client_for):
    admin = factories.admin_client
    responses = [
        await admin.put("/settings/search/jev", json={"api_key": KEY, "model": "jev-1.13.0"}),
        await admin.post("/settings/search/jev/test"),
        await admin.put("/settings/search/jev", json={"enabled": True}),
        await admin.get("/settings/search"),
        await admin.get("/features"),
        await admin.get("/settings/configuration"),
    ]
    for resp in responses:
        assert resp.status_code == 200, resp.text
        assert KEY not in resp.text
    jev_block = (await admin.get("/settings/search")).json()["jev"]
    assert jev_block["has_key"] is True and jev_block["key_last4"] == KEY[-4:]
    assert "api_key" not in jev_block and "api_key_encrypted" not in jev_block


@pytest.mark.parametrize("role", ["pm", "developer", "support"])
async def test_jev_settings_are_admin_and_cto_only(factories, client_for, role):
    client = await client_for(await factories.user(role=role))
    assert (await client.put("/settings/search/jev", json={"enabled": False})).status_code == 403
    assert (await client.post("/settings/search/jev/test")).status_code == 403


async def test_features_reflect_the_switch_for_every_role(factories, client_for):
    support = await client_for(await factories.user(role="support"))
    assert (await support.get("/features")).json() == {"jev_enabled": False}
    await enable_jev(factories.admin_client)
    assert (await support.get("/features")).json() == {"jev_enabled": True}


# ── Search (FR-S03, AC-S02–S04, BR-S04) ──────────────────────────────────────


async def test_jev_orders_results_and_ac_s03_below_threshold_goes_to_less_relevant(
    factories,
    project,
    reactions,
    jev,
):
    await enable_jev(factories.admin_client)
    scores = {
        reactions["group"].id: 0.93,
        reactions["private"].id: 0.62,
        reactions["edit"].id: 0.31,
    }
    jev.default(lambda key, q, state: {"type": "noul", "noul": scores[int(key[2:])]})

    body = await _search(factories.admin_client, "ری‌اکشن", project_id=project.id)
    assert body["jev_used"] is True
    assert _ids(body["results"]) == [reactions["group"].id, reactions["private"].id]
    assert _ids(body["less_relevant"]) == [reactions["edit"].id]
    # Jev only reorders and cuts stage-1 candidates (BR-S04), and never sees scores leak out.
    assert set(_rerank_ids(jev.calls[-1])) == {i.id for i in reactions.values()}
    assert all("jev" not in key for r in body["results"] for key in r)


async def test_no_close_matches_keeps_everything_in_less_relevant(
    factories, project, reactions, jev
):
    await enable_jev(factories.admin_client)
    jev.default(lambda key, q, state: {"type": "noul", "noul": 0.2})
    body = await _search(factories.admin_client, "ری‌اکشن", project_id=project.id)
    assert body["jev_used"] is True
    assert body["results"] == []
    assert set(_ids(body["less_relevant"])) == {i.id for i in reactions.values()}


async def test_rerank_payload_is_title_and_description_excerpt_only(
    factories, project, search_jobs, jev
):
    long_description = "ری‌اکشن " + "x" * 900
    item = await factories.issue(
        project_id=project.id, title=REACTION, description=long_description
    )
    await factories.admin_client.post(
        f"/issues/{item.id}/timeline",
        json={"body": "ری‌اکشن گروه internal-secret-note بعد از رفرش", "is_internal": True},
    )
    await search_jobs.run()
    await enable_jev(factories.admin_client)
    jev.calls.clear()
    await _search(factories.admin_client, "ری‌اکشن گروه", project_id=project.id)

    call = jev.calls[-1]
    assert call["state"] == "ری‌اکشن گروه" and call["model"] == "jev-1.13.0"
    issue = call["questions"][f"c_{item.id}"]["instructions"]["issue"]
    assert issue["title"] == REACTION
    assert len(issue["description"]) <= 401
    assert "internal-secret-note" not in str(call)


async def test_ac_s02_jev_timeout_falls_back_to_local_order(factories, project, reactions, jev):
    admin = factories.admin_client
    local = await _search(admin, "ری‌اکشن", project_id=project.id)  # Jev off: the local order
    await enable_jev(admin)
    jev.fail("timeout")
    body = await _search(admin, "ری‌اکشن", project_id=project.id)
    assert body["jev_used"] is False
    assert body["less_relevant"] == []
    assert _ids(body["results"]) == _ids(local["results"])


@pytest.mark.parametrize("mode", ["timeout", "http_401", "http_429", "http_500", "malformed"])
async def test_every_jev_failure_on_the_search_path_is_a_200_without_jev(
    factories,
    project,
    reactions,
    jev,
    mode,
):
    await enable_jev(factories.admin_client)
    jev.fail(mode)
    calls_before = len(jev.calls)
    body = await _search(factories.admin_client, "ری‌اکشن", project_id=project.id)
    assert body["jev_used"] is False and body["less_relevant"] == []
    assert {r["issue_id"] for r in body["results"]} == {i.id for i in reactions.values()}
    assert len(jev.calls) == calls_before + 1  # the request path never retries


async def test_ac_s04_palette_never_calls_jev(factories, project, reactions, jev):
    await enable_jev(factories.admin_client)
    jev.calls.clear()
    body = await _search(factories.admin_client, "ری‌اکشن", project_id=project.id, mode="palette")
    assert body["jev_used"] is False and body["results"]
    assert jev.calls == []


async def test_support_search_sends_jev_only_items_they_can_see(
    factories,
    project,
    client_for,
    search_jobs,
    jev,
):
    support = await factories.user(role="support")
    support_client = await client_for(support)
    template = await factories.support_template(project_id=project.id)
    visible = await factories.support_report(support_client, template=template, title=REACTION)
    internal = await factories.issue(project_id=project.id, title=REACTION + " (internal)")
    await search_jobs.run()
    await enable_jev(factories.admin_client)
    jev.calls.clear()

    body = await _search(support_client, "ری‌اکشن پیام گروه", project_id=project.id)
    assert _ids(body["results"] + body["less_relevant"]) == [visible.id]
    sent = {i for call in jev.calls for i in _rerank_ids(call)}
    assert sent == {visible.id} and internal.id not in sent


# ── Comment classification (FR-S16, A.6, BR-S14, AC-S17) ─────────────────────

GROUP_COMMENT = "The ری‌اکشن counter in group chat resets after a refresh, same root cause"


def _comment_label(label: str, confidence: float = 0.95):
    def answer(key, question, state):
        return {
            "type": "choice",
            "choice": label,
            "probabilities": {label: 1.0},
            "confidence": confidence,
        }

    return answer


async def test_with_jev_on_a_process_comment_is_not_indexed(factories, project, search_jobs, jev):
    await enable_jev(factories.admin_client)
    jev.script("kind", _comment_label("process"))
    item = await factories.issue(project_id=project.id, title="Checkout totals look wrong")
    await factories.admin_client.post(f"/issues/{item.id}/timeline", json={"body": GROUP_COMMENT})
    await search_jobs.run()
    assert any("kind" in c["questions"] for c in jev.calls)
    body = await _search(
        factories.admin_client, "ری‌اکشن counter group chat", project_id=project.id, mode="palette"
    )
    assert body["results"] == []


@pytest.mark.parametrize(
    "label,confidence,found",
    [
        ("this_problem", 0.9, True),
        ("other_problem", 0.9, True),  # kept, at half weight
        ("ack", 0.9, False),
        ("ack", 0.4, True),  # low confidence counts as used
    ],
)
async def test_jev_labels_decide_what_the_talk_channel_keeps(
    factories,
    project,
    search_jobs,
    jev,
    label,
    confidence,
    found,
):
    await enable_jev(factories.admin_client)
    jev.script("kind", _comment_label(label, confidence))
    item = await factories.issue(project_id=project.id, title="Checkout totals look wrong")
    await factories.admin_client.post(f"/issues/{item.id}/timeline", json={"body": GROUP_COMMENT})
    await search_jobs.run()
    body = await _search(
        factories.admin_client, "ری‌اکشن counter group chat", project_id=project.id, mode="palette"
    )
    assert (_ids(body["results"]) == [item.id]) is found


async def test_a_dropped_comment_never_reaches_jev(factories, project, search_jobs, jev):
    await enable_jev(factories.admin_client)
    item = await factories.issue(project_id=project.id, title="Checkout totals look wrong")
    await factories.admin_client.post(
        f"/issues/{item.id}/timeline",
        json={"body": "موافقم، هر وقت فرصت داشتید انجامش بدید"},
    )
    jev.calls.clear()
    await search_jobs.run()
    assert not any("kind" in c["questions"] for c in jev.calls)


async def test_a_failed_classification_falls_back_to_the_rule(factories, project, search_jobs, jev):
    await enable_jev(factories.admin_client)
    jev.fail("http_500")
    item = await factories.issue(project_id=project.id, title="Checkout totals look wrong")
    await factories.admin_client.post(f"/issues/{item.id}/timeline", json={"body": GROUP_COMMENT})
    await search_jobs.run()
    # A background job retries: 1 + JOB_RETRIES attempts, then the rule decides.
    assert sum(1 for c in jev.calls if "kind" in c["questions"]) == 1 + JOB_RETRIES
    jev.fail(None)
    body = await _search(
        factories.admin_client, "ری‌اکشن counter group chat", project_id=project.id, mode="palette"
    )
    assert _ids(body["results"]) == [item.id]
    status = (await factories.admin_client.get("/settings/search")).json()["jev"]
    assert status["backfill"]["remaining_rule_labels"] == 1  # the backfill will retry it


async def test_ac_s17_enabling_jev_backfills_only_rule_labels(
    factories,
    project,
    search_jobs,
    jev,
    background_jobs,
):
    item = await factories.issue(project_id=project.id, title="Checkout totals look wrong")
    admin = factories.admin_client
    await admin.post(f"/issues/{item.id}/timeline", json={"body": GROUP_COMMENT})
    await admin.post(f"/issues/{item.id}/timeline", json={"body": "ok, thanks!"})  # rule_dropped
    await search_jobs.run()
    q = "ری‌اکشن counter group chat"
    assert _ids((await _search(admin, q, project_id=project.id, mode="palette"))["results"]) == [
        item.id
    ]
    assert jev.calls == []  # Jev off: the rule classified both

    jev.script("kind", _comment_label("process"))
    await enable_jev(admin)
    assert len(background_jobs["backfill"]) == 1
    jev.calls.clear()
    await search_jobs.run()

    kinds = [c for c in jev.calls if "kind" in c["questions"]]
    assert len(kinds) == 1 and kinds[0]["state"]["comment"].startswith("The ری‌اکشن counter")
    # Reclassified as process → no longer searchable through the comment.
    assert (await _search(admin, q, project_id=project.id, mode="palette"))["results"] == []
    status = (await admin.get("/settings/search")).json()["jev"]
    assert status["backfill"]["remaining_rule_labels"] == 0
    assert status["backfill"]["done"] == 1 and status["backfill"]["running"] is False

    # Running it again changes nothing and calls Jev for nothing.
    from app.tasks.search_index import backfill_comment_classification_now

    jev.calls.clear()
    again = await backfill_comment_classification_now()
    assert again["total"] == 0 and jev.calls == []


async def test_backfill_ignores_a_workers_stale_off_cache(
    factories,
    project,
    search_jobs,
    jev,
):
    """The enabling PUT busts only the API process's cache, so a worker that
    cached "off" in the previous 30 s must not skip the backfill for good."""
    from time import monotonic

    from app.search import jev_settings

    item = await factories.issue(project_id=project.id, title="Checkout totals look wrong")
    admin = factories.admin_client
    await admin.post(f"/issues/{item.id}/timeline", json={"body": GROUP_COMMENT})
    await search_jobs.run()
    jev.script("kind", _comment_label("process"))
    await enable_jev(admin)

    jev_settings._cache["enabled"] = (monotonic(), False)  # a worker's stale view
    from app.tasks.search_index import backfill_comment_classification_now

    result = await backfill_comment_classification_now()
    assert "skipped" not in result and result["done"] == 1


async def test_disabling_jev_keeps_its_labels_and_new_comments_use_the_rule(
    factories,
    project,
    search_jobs,
    jev,
):
    admin = factories.admin_client
    await enable_jev(admin)
    jev.script("kind", _comment_label("process"))
    first = await factories.issue(project_id=project.id, title="Checkout totals look wrong")
    await admin.post(f"/issues/{first.id}/timeline", json={"body": GROUP_COMMENT})
    await search_jobs.run()

    assert (await admin.put("/settings/search/jev", json={"enabled": False})).status_code == 200
    second = await factories.issue(project_id=project.id, title="Invoice export broken")
    await admin.post(f"/issues/{second.id}/timeline", json={"body": GROUP_COMMENT})
    # Touch the first item too: its Jev label must survive a reindex while Jev is off.
    await admin.patch(f"/issues/{first.id}", json={"priority": "high"})
    jev.calls.clear()
    await search_jobs.run()

    assert jev.calls == []
    body = await _search(admin, "ری‌اکشن counter group chat", project_id=project.id)
    assert body["jev_used"] is False
    assert _ids(body["results"]) == [second.id]
