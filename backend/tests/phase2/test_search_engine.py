"""Slice 12 — the search engine, stage 1 (engine PRD FR-S01–S07, FR-S16/17/19).

Index jobs run through ``search_jobs`` (their bodies, called directly) against
the fake embedding endpoint (``tests/fakes/embedding_endpoint.py``), and every
assertion goes through ``GET /search`` or the settings API. The fake makes two
texts similar exactly when they share character trigrams, so fixture text is
chosen to be findable *by construction* — these tests assert behaviour
(inclusion, exclusion, obvious ordering), never model quality.
"""

import pytest

from app.tasks import search_index

REACTION_TITLE = "ری‌اکشن روی پیام‌های گروه ذخیره نمی‌شود"
REACTION_DESC = "بعد از زدن reaction در group chat و رفرش صفحه، ری‌اکشن پاک می‌شود."
SIGNUP_TITLE = "ثبت‌نام زبان‌آموز در کلاس آنلاین انجام نمی‌شود"
LOGIN_TITLE = "Login page crashes on Safari when the password is empty"


async def _search(client, q, **params):
    resp = await client.get("/search", params={"q": q, **params})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _ids(body):
    return [r["issue_id"] for r in body["results"]]


@pytest.fixture
async def project(factories):
    return await factories.project()


@pytest.fixture
async def corpus(factories, project, search_jobs):
    """Three unrelated items in one project, indexed."""
    reaction = await factories.issue(
        project_id=project.id,
        title=REACTION_TITLE,
        description=REACTION_DESC,
    )
    signup = await factories.issue(project_id=project.id, title=SIGNUP_TITLE)
    login = await factories.issue(
        project_id=project.id,
        title=LOGIN_TITLE,
        description="Calls `/api/v1/auth/login` and the server answers 413.",
    )
    await search_jobs.run()
    return {"reaction": reaction, "signup": signup, "login": login}


# ── Matching (FR-S07) ────────────────────────────────────────────────────────


async def test_ac_s01_cross_script_query_finds_item(factories, project, corpus):
    body = await _search(
        factories.admin_client, "مشکل در reaction در group chat", project_id=project.id
    )
    assert corpus["reaction"].id in _ids(body)[:5]
    assert body["less_relevant"] == []
    assert body["jev_used"] is False


async def test_one_word_query_finds_the_feature(factories, project, corpus):
    body = await _search(factories.admin_client, "ری‌اکشن", project_id=project.id)
    assert _ids(body)[0] == corpus["reaction"].id


async def test_missing_half_spaces_are_tolerated(factories, project, corpus):
    body = await _search(factories.admin_client, "ثبتنام زبان اموز", project_id=project.id)
    assert _ids(body)[0] == corpus["signup"].id


async def test_arabic_letter_variants_match(factories, project, corpus):
    body = await _search(factories.admin_client, "ثبتنام زبان اموز در كلاس", project_id=project.id)
    assert _ids(body)[0] == corpus["signup"].id


async def test_endpoint_paths_and_error_codes_are_findable(factories, project, corpus):
    for q in ("/api/v1/auth/login", "413"):
        body = await _search(factories.admin_client, q, project_id=project.id)
        assert _ids(body) == [corpus["login"].id], q
        assert "keyword" in body["results"][0]["matched_via"]


async def test_unrelated_query_returns_nothing(factories, project, corpus):
    """FR-S04: below the floor is left out, so an empty page means "not reported yet"."""
    body = await _search(factories.admin_client, "invoice export broken", project_id=project.id)
    assert body["results"] == []


# ── Scope, filters, result shape (FR-S01, FR-S02, FR-S06) ────────────────────


async def test_search_covers_the_project_by_default_and_all_projects_on_request(
    factories,
    project,
    search_jobs,
):
    other = await factories.project()
    here = await factories.issue(project_id=project.id, title=SIGNUP_TITLE)
    there = await factories.issue(project_id=other.id, title=SIGNUP_TITLE + " دوباره")
    await search_jobs.run()

    client = factories.admin_client
    assert _ids(await _search(client, "ثبت‌نام زبان‌آموز", project_id=project.id)) == [here.id]
    assert set(_ids(await _search(client, "ثبت‌نام زبان‌آموز", scope="all"))) == {here.id, there.id}

    resp = await client.get("/search", params={"q": "ثبت‌نام"})
    assert resp.status_code == 422


async def test_filters_by_type_and_status(factories, project, search_jobs):
    bug = await factories.issue(project_id=project.id, title=SIGNUP_TITLE)
    task = await factories.issue(project_id=project.id, type="task", title=SIGNUP_TITLE + " (task)")
    await search_jobs.run()
    client = factories.admin_client

    assert _ids(await _search(client, "ثبت‌نام زبان‌آموز", project_id=project.id, type="task")) == [
        task.id
    ]
    assert _ids(await _search(client, "ثبت‌نام زبان‌آموز", project_id=project.id, type="bug")) == [
        bug.id
    ]
    assert _ids(await _search(client, "ثبت‌نام زبان‌آموز", project_id=project.id, status="new")) == [
        bug.id
    ]


async def test_result_rows_carry_key_type_title_status_project_and_snippet(
    factories, project, corpus
):
    body = await _search(factories.admin_client, "ری‌اکشن", project_id=project.id)
    row = body["results"][0]
    assert row["key"] == f"BUG-{corpus['reaction'].issue_number}"
    assert row["type"] == "bug"
    assert row["title"] == REACTION_TITLE
    assert row["status"] == "new"
    assert row["project"] == {"id": project.id, "name": project.name, "slug": project.slug}
    assert row["snippet"].startswith("بعد از زدن reaction")
    assert row["snippet_source"] == "description"
    assert row["is_cancelled"] is False


async def test_ac_s06_cancelled_item_searchable_and_marked(factories, project, search_jobs):
    item = await factories.issue(project_id=project.id, title=SIGNUP_TITLE)
    resp = await factories.admin_client.post(
        f"/issues/{item.id}/transition",
        json={"to": "cancelled", "cancel_reason": "wont_fix"},
    )
    assert resp.status_code == 200, resp.text
    await search_jobs.run()

    body = await _search(factories.admin_client, SIGNUP_TITLE, project_id=project.id)
    assert _ids(body) == [item.id]
    assert body["results"][0]["status"] == "cancelled"
    assert body["results"][0]["is_cancelled"] is True


async def test_snippet_comes_from_the_comment_that_matched(factories, project, search_jobs):
    item = await factories.issue(project_id=project.id, title="Checkout totals look wrong")
    comment = "The ری‌اکشن counter in group chat resets after a refresh, same root cause"
    resp = await factories.admin_client.post(f"/issues/{item.id}/timeline", json={"body": comment})
    assert resp.status_code == 201, resp.text
    await search_jobs.run()

    page = await _search(factories.admin_client, "ری‌اکشن counter group chat", project_id=project.id)
    assert _ids(page) == [item.id]
    assert page["results"][0]["snippet_source"] == "comment"
    assert page["results"][0]["snippet"] == comment
    assert "talk" in page["results"][0]["matched_via"]

    palette = await _search(
        factories.admin_client,
        "ری‌اکشن counter group chat",
        project_id=project.id,
        mode="palette",
    )
    assert _ids(palette) == [item.id]
    assert palette["results"][0]["snippet_source"] != "comment"


async def test_palette_mode_returns_at_most_eight(factories, project, search_jobs):
    for n in range(10):
        await factories.issue(project_id=project.id, title=f"{SIGNUP_TITLE} {n}")
    await search_jobs.run()
    page = await _search(factories.admin_client, "ثبت‌نام زبان‌آموز", project_id=project.id)
    palette = await _search(
        factories.admin_client, "ثبت‌نام زبان‌آموز", project_id=project.id, mode="palette"
    )
    assert len(page["results"]) == 10
    assert len(palette["results"]) == 8
    assert palette["less_relevant"] == [] and palette["jev_used"] is False


async def test_deleted_item_leaves_the_results(factories, project, corpus, search_jobs):
    resp = await factories.admin_client.delete(f"/issues/{corpus['signup'].id}")
    assert resp.status_code == 204, resp.text
    await search_jobs.run()
    assert _ids(await _search(factories.admin_client, SIGNUP_TITLE, project_id=project.id)) == []


async def test_search_still_answers_by_keyword_when_the_embedding_service_is_down(
    factories,
    project,
    corpus,
    embedding_endpoint,
):
    embedding_endpoint.fail = True
    body = await _search(factories.admin_client, "/api/v1/auth/login", project_id=project.id)
    assert _ids(body) == [corpus["login"].id]
    assert body["results"][0]["matched_via"] == ["keyword"]
    # Nothing dense to go on: no error, just fewer results.
    assert (await _search(factories.admin_client, "invoice export broken", project_id=project.id))[
        "results"
    ] == []


# ── Visibility (BR-S06, AC-S05) ──────────────────────────────────────────────


async def test_ac_s05_support_never_matches_through_internal_notes(
    factories,
    project,
    client_for,
    search_jobs,
):
    support = await factories.user(role="support")
    support_client = await client_for(support)
    template = await factories.support_template(project_id=project.id)

    # A support report whose only match is an internal note.
    hidden = await factories.support_report(
        support_client, template=template, title="Payment page is slow"
    )
    note = "ری‌اکشن روی پیام‌های گروه بعد از رفرش پاک می‌شود"
    resp = await factories.admin_client.post(
        f"/issues/{hidden.id}/timeline",
        json={"body": note, "is_internal": True},
    )
    assert resp.status_code == 201, resp.text
    # A matching internal bug and a matching task — not Support's to see.
    bug = await factories.issue(project_id=project.id, title=REACTION_TITLE)
    task = await factories.issue(
        project_id=project.id, type="task", title=REACTION_TITLE + " (task)"
    )
    # A support report that matches publicly: the control.
    visible = await factories.support_report(
        support_client, template=template, title=REACTION_TITLE
    )
    await search_jobs.run()

    body = await _search(support_client, "ری‌اکشن پیام‌های گروه", project_id=project.id)
    assert _ids(body) == [visible.id]
    assert all(r["snippet_source"] != "comment" for r in body["results"])

    # The same query as a tech user finds all four, the hidden one through its note.
    tech = await _search(factories.admin_client, "ری‌اکشن پیام‌های گروه", project_id=project.id)
    assert set(_ids(tech)) == {hidden.id, bug.id, task.id, visible.id}
    hidden_row = next(r for r in tech["results"] if r["issue_id"] == hidden.id)
    assert hidden_row["snippet_source"] == "comment"


# ── Comment classification (FR-S16, AC-S16) ──────────────────────────────────


async def test_ac_s16_ack_comment_not_indexed(factories, project, search_jobs, embedding_endpoint):
    item = await factories.issue(project_id=project.id, title="Checkout totals look wrong")
    ack = "موافقم، هر وقت فرصت داشتید انجامش بدید"
    resp = await factories.admin_client.post(f"/issues/{item.id}/timeline", json={"body": ack})
    assert resp.status_code == 201, resp.text
    await search_jobs.run()

    assert ack not in embedding_endpoint.texts
    body = await _search(
        factories.admin_client, "هر وقت فرصت داشتید انجامش بدید", project_id=project.id
    )
    assert body["results"] == []


async def test_editing_and_deleting_a_comment_updates_the_index(factories, project, search_jobs):
    item = await factories.issue(project_id=project.id, title="Checkout totals look wrong")
    resp = await factories.admin_client.post(
        f"/issues/{item.id}/timeline",
        json={"body": "ok"},
    )
    event_id = resp.json()["id"]
    await search_jobs.run()
    q = "ری‌اکشن counter group chat"
    assert _ids(await _search(factories.admin_client, q, project_id=project.id)) == []

    resp = await factories.admin_client.patch(
        f"/issues/{item.id}/timeline/{event_id}",
        json={"body": "The ری‌اکشن counter in group chat resets after a refresh"},
    )
    assert resp.status_code == 200, resp.text
    await search_jobs.run()
    assert _ids(await _search(factories.admin_client, q, project_id=project.id)) == [item.id]

    resp = await factories.admin_client.delete(f"/issues/{item.id}/timeline/{event_id}")
    assert resp.status_code == 204, resp.text
    await search_jobs.run()
    assert _ids(await _search(factories.admin_client, q, project_id=project.id)) == []


# ── Reindexing (BR-S17, AC-S15) ──────────────────────────────────────────────


async def test_ac_s15_title_edit_reembeds_title_body_not_talk(
    factories,
    project,
    search_jobs,
    embedding_endpoint,
):
    item = await factories.issue(
        project_id=project.id, title=SIGNUP_TITLE, description="Short note."
    )
    comment = "The enrolment API returns 500 for learners in the online class"
    await factories.admin_client.post(f"/issues/{item.id}/timeline", json={"body": comment})
    await search_jobs.run()
    assert comment in embedding_endpoint.texts

    embedding_endpoint.requests.clear()
    resp = await factories.admin_client.patch(
        f"/issues/{item.id}",
        json={"title": "ثبت‌نام زبان‌آموز در کلاس حضوری انجام نمی‌شود"},
    )
    assert resp.status_code == 200, resp.text
    await search_jobs.run()

    embedded = embedding_endpoint.texts
    assert "ثبت‌نام زبان‌آموز در کلاس حضوری انجام نمی‌شود" in embedded  # title
    assert any(
        t.startswith("ثبت‌نام زبان‌آموز در کلاس حضوری") and "Short note." in t for t in embedded
    )  # body
    assert comment not in embedded  # talk unchanged
    body = await _search(factories.admin_client, "کلاس حضوری", project_id=project.id)
    assert _ids(body) == [item.id]


async def test_an_unchanged_item_is_not_reembedded(
    factories, project, search_jobs, embedding_endpoint
):
    item = await factories.issue(project_id=project.id, title=SIGNUP_TITLE)
    await search_jobs.run()
    embedding_endpoint.requests.clear()
    resp = await factories.admin_client.patch(f"/issues/{item.id}", json={"priority": "high"})
    assert resp.status_code == 200, resp.text
    await search_jobs.run()
    assert embedding_endpoint.texts == []


async def test_writes_enqueue_after_commit_and_are_debounced(factories, project, background_jobs):
    item = await factories.issue(project_id=project.id, title=SIGNUP_TITLE)
    assert [args for args, _, _ in background_jobs["index_item"]] == [(item.id,)]
    _, _, options = background_jobs["index_item"][0]
    assert options["countdown"] == search_index.DEBOUNCE_SECONDS
    assert options["queue"] == "search"

    for title in ("one", "two"):
        resp = await factories.admin_client.patch(
            f"/issues/{item.id}", json={"title": f"{SIGNUP_TITLE} {title}"}
        )
        assert resp.status_code == 200
    # Still one job waiting for the item: the edits ride along with it.
    assert len(background_jobs["index_item"]) == 1


async def test_a_rolled_back_write_enqueues_nothing(db_session, background_jobs):
    from sqlalchemy import text

    await db_session.execute(text("SELECT 1"))  # a write in progress
    search_index.enqueue(db_session, 4242)
    await db_session.rollback()
    await db_session.execute(text("SELECT 1"))
    await db_session.commit()
    assert background_jobs["index_item"] == []

    await db_session.execute(text("SELECT 1"))
    search_index.enqueue(db_session, 4242)
    await db_session.commit()
    assert [args for args, _, _ in background_jobs["index_item"]] == [(4242,)]


# ── Settings → Search (FR-S17, FR-S19, AC-S18, AC-S21) ───────────────────────


async def test_search_settings_show_endpoint_model_and_progress(
    factories, project, corpus, search_jobs
):
    await factories.issue(project_id=project.id, title="Not indexed yet")
    resp = await factories.admin_client.get("/settings/search")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["embedding_endpoint"] == "http://fake-embeddings/v1"
    assert body["is_default_endpoint"] is True
    assert body["embed_model"] == "fake/fake-embeddings"
    assert body["service"] == {"reachable": True, "model": "fake/fake-embeddings", "error": None}
    assert body["index"]["indexed"] == 3 and body["index"]["total"] == 4
    # No reindex has run: the index is incomplete, not "in progress".
    assert body["index"]["in_progress"] is False
    assert body["index"]["incomplete"] is True

    resp = await factories.admin_client.post("/settings/search/reindex")
    assert resp.status_code == 202 and resp.json() == {"reindex_started": True}
    await search_jobs.run()
    body = (await factories.admin_client.get("/settings/search")).json()
    assert body["index"]["indexed"] == body["index"]["total"] == 4
    assert body["index"]["in_progress"] is False
    assert body["index"]["incomplete"] is False
    assert body["index"]["last_run_at"] is not None


async def test_a_reindex_run_shows_in_progress_until_every_item_is_indexed(
    factories, project, search_jobs, background_jobs,
):
    await factories.issue(project_id=project.id, title=SIGNUP_TITLE)
    await factories.issue(project_id=project.id, title=LOGIN_TITLE)
    await search_index.reindex_all_now()  # the run starts; the item jobs are still queued
    index = (await factories.admin_client.get("/settings/search")).json()["index"]
    assert index["in_progress"] is True and index["incomplete"] is False

    await search_jobs.run()
    index = (await factories.admin_client.get("/settings/search")).json()["index"]
    assert index["in_progress"] is False and index["indexed"] == 2


async def test_ac_s18_model_change_triggers_reindex_and_isolates_models(
    factories,
    project,
    corpus,
    search_jobs,
    background_jobs,
):
    client = factories.admin_client
    assert _ids(await _search(client, "ری‌اکشن", project_id=project.id)) == [corpus["reaction"].id]

    resp = await client.put(
        "/settings/search", json={"embedding_endpoint": "http://other-model/v1"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["reindex_started"] is True
    assert len(background_jobs["reindex_all"]) == 1

    # Until the reindex runs, the old model's vectors are never compared with
    # the new model's query vector: nothing is found rather than something wrong.
    assert (await _search(client, "ری‌اکشن", project_id=project.id))["results"] == []

    await search_jobs.run()
    assert _ids(await _search(client, "ری‌اکشن", project_id=project.id)) == [corpus["reaction"].id]
    body = (await client.get("/settings/search")).json()
    assert body["embed_model"] == "fake/other-model"
    assert body["index"]["indexed"] == body["index"]["total"] == 3


async def test_a_model_swapped_behind_the_same_endpoint_is_noticed(
    factories,
    project,
    corpus,
    search_jobs,
    background_jobs,
    monkeypatch,
):
    """The service reports a new model while indexing → reindex, never mix (BR-S16)."""
    from app.config import settings

    background_jobs["reindex_all"].clear()
    monkeypatch.setattr(settings, "SEARCH_EMBEDDING_ENDPOINT", "http://swapped/v1")
    resp = await factories.admin_client.patch(
        f"/issues/{corpus['signup'].id}", json={"title": SIGNUP_TITLE + "!"}
    )
    assert resp.status_code == 200
    await search_index.index_item_now(corpus["signup"].id)
    assert len(background_jobs["reindex_all"]) == 1
    await search_jobs.run()
    body = (await factories.admin_client.get("/settings/search")).json()
    assert body["embed_model"] == "fake/swapped"
    assert body["index"]["indexed"] == 3


async def test_a_model_swap_seen_by_a_query_starts_a_reindex(
    factories, project, corpus, search_jobs, background_jobs, monkeypatch,
):
    from app.config import settings

    monkeypatch.setattr(settings, "SEARCH_EMBEDDING_ENDPOINT", "http://swapped/v1")
    body = await _search(factories.admin_client, "ری‌اکشن", project_id=project.id)
    assert body["results"] == []  # never compared across models
    assert len(background_jobs["reindex_all"]) == 1
    await search_jobs.run()
    body = await _search(factories.admin_client, "ری‌اکشن", project_id=project.id)
    assert _ids(body) == [corpus["reaction"].id]


async def test_an_unreachable_endpoint_is_refused(factories, embedding_endpoint, background_jobs):
    embedding_endpoint.fail = True
    resp = await factories.admin_client.put(
        "/settings/search", json={"embedding_endpoint": "http://down/v1"}
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "embedding_endpoint_unreachable"
    assert background_jobs["reindex_all"] == []

    embedding_endpoint.fail = False
    embedding_endpoint.dim = 768
    resp = await factories.admin_client.put(
        "/settings/search", json={"embedding_endpoint": "http://small/v1"}
    )
    assert resp.status_code == 422
    assert "1024" in resp.json()["detail"]


async def test_saving_the_same_endpoint_does_not_reindex(
    factories, project, corpus, background_jobs
):
    resp = await factories.admin_client.put(
        "/settings/search",
        json={"embedding_endpoint": "http://fake-embeddings/v1/"},
    )
    assert resp.status_code == 200
    assert resp.json()["reindex_started"] is False
    assert resp.json()["is_default_endpoint"] is True


async def test_api_key_and_model_are_sent_stored_encrypted_and_never_returned(
    factories, project, corpus, embedding_endpoint, background_jobs
):
    secret = "sk-test-1234567890abcd"
    resp = await factories.admin_client.put(
        "/settings/search",
        json={
            "embedding_endpoint": "http://fake-embeddings/v1",
            "embedding_model": "text-embedding-3-small",
            "api_key": secret,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["embedding_model"] == "text-embedding-3-small"
    assert body["has_key"] is True and body["key_last4"] == "abcd"
    assert secret not in resp.text

    # The probe carried the key, the typed model and the index's dimensions.
    assert embedding_endpoint.auth[-1] == f"Bearer {secret}"
    assert embedding_endpoint.payloads[-1]["model"] == "text-embedding-3-small"
    assert embedding_endpoint.payloads[-1]["dimensions"] == 1024

    # A later PUT that omits the key and model keeps both.
    resp = await factories.admin_client.put(
        "/settings/search", json={"embedding_endpoint": "http://fake-embeddings/v1"}
    )
    assert resp.json()["has_key"] is True
    assert resp.json()["embedding_model"] == "text-embedding-3-small"
    assert secret not in (await factories.admin_client.get("/settings/search")).text

    # An empty key clears it; no key means no Authorization header.
    resp = await factories.admin_client.put(
        "/settings/search",
        json={"embedding_endpoint": "http://fake-embeddings/v1", "api_key": "", "embedding_model": ""},
    )
    assert resp.json()["has_key"] is False and resp.json()["embedding_model"] == ""
    assert embedding_endpoint.auth[-1] is None
    assert "dimensions" not in embedding_endpoint.payloads[-1]


async def test_cto_can_open_and_change_search_settings(factories, client_for, background_jobs):
    cto = await client_for(await factories.user(role="cto"))
    assert (await cto.get("/settings/search")).status_code == 200
    resp = await cto.put(
        "/settings/search", json={"embedding_endpoint": "http://fake-embeddings/v1"}
    )
    assert resp.status_code == 200, resp.text
    assert (await cto.post("/settings/search/reindex")).status_code == 202


@pytest.mark.parametrize("role", ["product_manager", "developer", "qa", "support"])
async def test_ac_s21_search_settings_admin_and_cto_only(factories, client_for, role):
    client = await client_for(await factories.user(role=role))
    assert (await client.get("/settings/search")).status_code == 403
    assert (
        await client.put("/settings/search", json={"embedding_endpoint": "http://x/v1"})
    ).status_code == 403
    assert (await client.post("/settings/search/reindex")).status_code == 403


async def test_features_reports_jev_off(factories, client_for):
    client = await client_for(await factories.user(role="support"))
    resp = await client.get("/features")
    assert resp.status_code == 200
    assert resp.json() == {"jev_enabled": False}


async def test_worker_start_reindexes_an_empty_index(
    factories, project, background_jobs, search_jobs
):
    assert await search_index.bootstrap_if_empty() is False  # nothing to index
    await factories.issue(project_id=project.id, title=SIGNUP_TITLE)
    assert await search_index.bootstrap_if_empty() is True
    assert len(background_jobs["reindex_all"]) == 1
    await search_jobs.run()
    assert await search_index.bootstrap_if_empty() is False
