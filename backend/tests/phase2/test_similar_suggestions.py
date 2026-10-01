"""Slice 14 — similar-item suggestions and triage merge hints.

docs/phase-2/14-similar-item-suggestions.md (FR-S08–S15, BR-S02/03/07–S12,
S21, AC-S07–S14; PRD v3 BR-49/50). Jev is the fake from ``tests/fakes/jev.py``
(autouse ``jev``), embeddings the fake endpoint, index and hint jobs run
through ``search_jobs``. Jev is switched on the way an Admin does it.

The fake's default choice answer is ``same`` at 0.95 — exactly what a hint or
a panel needs — so tests script Jev only to make a candidate ``related`` or
``unrelated``, or to fail.
"""

import pytest

KEY = "tsk-test-0123456789abcdef"

# A family of titles about the same problem (reactions lost in group chat),
# written the way two different people would write them, and an unrelated
# payment family — the fake endpoint's trigram vectors rank these apart.
REACTION_SEEDED = "ری‌اکشن روی پیام‌های گروه ذخیره نمی‌شود"
REACTION_DRAFT = "ری‌اکشن های گروه بعد از رفرش ذخیره نمی‌شود"
REACTION_VARIANT = "ذخیره نشدن ری‌اکشن پیام گروه"
PAYMENT_SEEDED = "پرداخت در صفحه تسویه با خطا شکست می‌خورد"
PAYMENT_DRAFT = "دکمه پرداخت تسویه بعد از کلیک خطا میدهد"

TRIAGE_QUEUE = {"statuses": "new,needs_info", "sort": "oldest"}


async def enable_jev(admin, key: str = KEY) -> None:
    assert (await admin.put("/settings/search/jev", json={"api_key": key})).status_code == 200
    test = await admin.post("/settings/search/jev/test")
    assert test.status_code == 200 and test.json()["ok"], test.text
    resp = await admin.put("/settings/search/jev", json={"enabled": True})
    assert resp.status_code == 200, resp.text


async def disable_jev(admin) -> None:
    resp = await admin.put("/settings/search/jev", json={"enabled": False})
    assert resp.status_code == 200, resp.text


def _choice(label: str, confidence: float = 0.9) -> dict:
    return {
        "type": "choice",
        "choice": label,
        "probabilities": {label: confidence},
        "confidence": confidence,
    }


def judge_by_title(key: str, question: dict, state) -> dict:
    """A realistic default judge: ``same`` iff draft and candidate are from the
    same problem family (reactions / payments), else ``unrelated``. Questions
    that are not the same-problem judge (the settings ping) answer 0.9."""
    if question.get("type") != "choice" or "existing_issue" not in question.get("instructions", {}):
        return {"type": "noul", "noul": 0.9}
    existing = question["instructions"]["existing_issue"]["title"]
    draft = state["new_report"]["title"]
    families = (("ری‌اکشن", "ری‌اکشن"), ("پرداخت", "پرداخت"))
    same = any(a in existing and b in draft for a, b in families)
    return _choice("same" if same else "unrelated", 0.9)


async def similar(client, body: dict):
    return await client.post("/search/similar", json=body)


async def hints(client, issue_id: int) -> dict:
    resp = await client.get(f"/issues/{issue_id}/duplicate-hints")
    assert resp.status_code == 200, resp.text
    return resp.json()


async def dismiss(client, issue_id: int, candidate_id: int):
    return await client.post(f"/issues/{issue_id}/duplicate-hints/{candidate_id}/dismiss")


async def queue_row(client, issue_id: int, project_id: int) -> dict | None:
    resp = await client.get(
        "/issues", params={**TRIAGE_QUEUE, "project_id": project_id, "size": 100},
    )
    assert resp.status_code == 200, resp.text
    return next((i for i in resp.json()["items"] if i["id"] == issue_id), None)


async def triage(client, issue_id: int, **body):
    return await client.post(f"/issues/{issue_id}/triage", json=body)


async def to_status(client, issue_id: int, to: str, **extra):
    resp = await client.post(f"/issues/{issue_id}/transition", json={"to": to, **extra})
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest.fixture
async def rig(factories, client_for):
    lead = await factories.user(role="developer", name="Lead Dev")
    support = await factories.user(role="support")
    qa = await factories.user(role="qa")
    project = await factories.project(triage_lead_id=lead.id)
    template = await factories.support_template(project_id=project.id)
    return {
        "admin": factories.admin_client,
        "lead": lead, "lead_client": await client_for(lead),
        "qa": qa, "qa_client": await client_for(qa),
        "support": support, "support_client": await client_for(support),
        "project": project,
        "template": template,
    }


@pytest.fixture
async def reaction_world(factories, rig, search_jobs):
    """An indexed project with one open support report about reactions, plus
    the items the panels must never suggest: a done one, a cancelled one, an
    internal bug, and the same problem in another project."""
    report = await factories.support_report(
        rig["support_client"], template=rig["template"], title=REACTION_SEEDED,
    )
    done = await factories.support_report(
        rig["support_client"], template=rig["template"], title=REACTION_VARIANT,
    )
    await triage(rig["lead_client"], done.id, outcome="accept", priority="high")
    await to_status(rig["admin"], done.id, "done")
    cancelled = await factories.support_report(
        rig["support_client"], template=rig["template"], title=REACTION_VARIANT,
    )
    await triage(rig["lead_client"], cancelled.id, outcome="reject", reason="user_error")
    internal = await factories.issue(
        project_id=rig["project"].id, title=REACTION_VARIANT,
    )
    other_project = await factories.project()
    other_template = await factories.support_template(project_id=other_project.id)
    other = await factories.support_report(
        rig["support_client"], template=other_template, title=REACTION_SEEDED,
    )
    await search_jobs.run()
    return {
        "report": report, "done": done, "cancelled": cancelled,
        "internal": internal, "other": other, "other_project": other_project,
    }


# ── AC-S07: Jev off — no panels, no hints, no markers ────────────────────────


async def test_ac_s07_no_panels_or_hints_when_jev_disabled(
    factories, rig, reaction_world, search_jobs,
):
    new_bug = await factories.issue(project_id=rig["project"].id, title=REACTION_DRAFT)
    await search_jobs.run()

    resp = await similar(rig["support_client"], {
        "context": "support", "project_id": rig["project"].id,
        "title": REACTION_DRAFT, "template_id": rig["template"].id, "values": {},
    })
    assert resp.status_code == 204

    resp = await similar(rig["qa_client"], {
        "context": "tech", "project_id": rig["project"].id, "title": REACTION_DRAFT,
    })
    assert resp.status_code == 204

    assert (await hints(rig["qa_client"], new_bug.id))["hints"] == []
    row = await queue_row(rig["lead_client"], new_bug.id, rig["project"].id)
    assert row is not None and row["possible_duplicates_count"] == 0


# ── AC-S08: the support panel's candidates ───────────────────────────────────


async def test_ac_s08_support_candidates_open_support_same_project_only(
    factories, rig, reaction_world, jev,
):
    await enable_jev(factories.admin_client)
    resp = await similar(rig["support_client"], {
        "context": "support", "project_id": rig["project"].id,
        "title": REACTION_DRAFT,
        "template_id": rig["template"].id,
        "values": {str(f["id"]): "بعد از رفرش ری‌اکشن ها میپرند" for f in rig["template"].fields},
        "description": "مشکل در چت گروه",
    })
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert [i["issue"]["id"] for i in items] == [reaction_world["report"].id]
    assert items[0]["verdict"] == "same" and items[0]["confidence"] >= 0.7
    # The draft Jev judged is the composed report, template block included.
    state = jev.calls[-1]["state"]["new_report"]
    assert state["title"] == REACTION_DRAFT
    assert "Report template" in state["description"]
    assert "بعد از رفرش" in state["description"]


async def test_support_panel_shows_same_only_not_related(factories, rig, reaction_world, jev):
    await enable_jev(factories.admin_client)
    jev.script("c_", _choice("related", 0.9))

    resp = await similar(rig["support_client"], {
        "context": "support", "project_id": rig["project"].id,
        "title": REACTION_DRAFT, "template_id": rig["template"].id,
    })
    assert resp.status_code == 200 and resp.json()["items"] == []

    # The tech form shows the same related items for information (FR-S08).
    resp = await similar(rig["qa_client"], {
        "context": "tech", "project_id": rig["project"].id, "title": REACTION_DRAFT,
    })
    items = resp.json()["items"]
    assert items and all(i["verdict"] == "related" for i in items)

    # …but only at T_RELATED or above.
    jev.script("c_", _choice("related", 0.55))
    resp = await similar(rig["qa_client"], {
        "context": "tech", "project_id": rig["project"].id, "title": REACTION_DRAFT,
    })
    assert resp.json()["items"] == []


async def test_support_cannot_use_the_tech_context(factories, rig, reaction_world):
    resp = await similar(rig["support_client"], {
        "context": "tech", "project_id": rig["project"].id, "title": REACTION_DRAFT,
    })
    assert resp.status_code == 403


@pytest.mark.parametrize("mode", ["timeout", "http_401", "http_429", "http_500", "malformed"])
async def test_similar_returns_204_on_each_jev_failure_mode(
    factories, rig, reaction_world, jev, mode,
):
    await enable_jev(factories.admin_client)
    jev.fail(mode)
    resp = await similar(rig["qa_client"], {
        "context": "tech", "project_id": rig["project"].id, "title": REACTION_DRAFT,
    })
    assert resp.status_code == 204
    jev.fail(None)


# ── AC-S09: record recurrence from the panel (07's endpoint, unchanged) ──────


async def test_ac_s09_support_records_recurrence_from_panel(factories, rig, reaction_world):
    report = reaction_world["report"]
    before = (await rig["admin"].get(f"/issues/{report.id}")).json()["recurrence_count"]

    composed = (
        "**Report template:** Online class problem\n\n"
        "- **What happened:** بعد از رفرش ری‌اکشن ها میپرند\n\n---\n\nمشکل در چت گروه"
    )
    resp = await rig["support_client"].post(f"/issues/{report.id}/recurrences", json={
        "comment": composed,
        "pending_attachments": [{
            "s3_key": "pending/abc/reaction.png", "filename": "reaction.png",
            "mime_type": "image/png", "file_size_bytes": 99, "attachment_type": "screenshot",
        }],
    })
    assert resp.status_code == 201, resp.text
    after = (await rig["admin"].get(f"/issues/{report.id}")).json()
    assert after["recurrence_count"] == before + 1
    files = (await rig["support_client"].get(f"/issues/{report.id}/attachments")).json()
    assert [f["file_name"] for f in files] == ["reaction.png"]
    # No new report was created: the project's queue grew by nothing.
    row = await queue_row(rig["lead_client"], report.id, rig["project"].id)
    assert row is not None and row["recurrence_count"] == before + 1


# ── AC-S10–S13: stored hints, merge effects, dismissal ───────────────────────


async def test_ac_s10_new_bug_gets_possible_duplicate_hint(
    factories, rig, reaction_world, jev, search_jobs,
):
    jev.default(judge_by_title)
    await enable_jev(factories.admin_client)
    new_bug = await factories.issue(project_id=rig["project"].id, title=REACTION_DRAFT)
    await search_jobs.run()

    body = await hints(rig["qa_client"], new_bug.id)
    world = reaction_world
    # Every same-problem item of the project that may be merged into: the open
    # report, the Done one (merging returns it), the internal bug — never the
    # cancelled one, never the other project, at most three (FR-S12).
    assert {h["candidate"]["id"] for h in body["hints"]} == {
        world["report"].id, world["done"].id, world["internal"].id,
    }
    by_id = {h["candidate"]["id"]: h for h in body["hints"]}
    assert by_id[world["report"].id]["candidate"]["status"] == "new"
    assert by_id[world["report"].id]["candidate"]["key"].startswith("BUG-")
    assert by_id[world["report"].id]["merge_effect"] == "unchanged"
    assert by_id[world["done"].id]["merge_effect"] in ("returns_release_qa", "returns_production")

    row = await queue_row(rig["lead_client"], new_bug.id, rig["project"].id)
    assert row is not None and row["possible_duplicates_count"] == len(body["hints"])


async def test_ac_s11_hint_on_done_candidate_says_return_and_merge_returns(
    factories, rig, jev, search_jobs,
):
    jev.default(judge_by_title)
    await enable_jev(factories.admin_client)
    stream_id = await factories.stream_id(project_id=rig["project"].id)
    stream_bug = await factories.issue(project_id=rig["project"].id, title=REACTION_SEEDED)
    await triage(
        rig["lead_client"], stream_bug.id, outcome="accept",
        priority="high", release_id=stream_id,
    )
    await to_status(rig["admin"], stream_bug.id, "done")

    release = await factories.release(project_id=rig["project"].id)
    await factories.set_release_status(release.id, "qa")
    release_bug = await factories.issue(
        project_id=rig["project"].id, release_id=release.id, title=PAYMENT_SEEDED,
    )
    await triage(rig["lead_client"], release_bug.id, outcome="accept", priority="high")
    await to_status(rig["admin"], release_bug.id, "done")
    await search_jobs.run()

    dup_of_stream = await factories.issue(project_id=rig["project"].id, title=REACTION_DRAFT)
    dup_of_release = await factories.issue(project_id=rig["project"].id, title=PAYMENT_DRAFT)
    await search_jobs.run()

    by_candidate = {
        h["candidate"]["id"]: h
        for h in (await hints(rig["qa_client"], dup_of_stream.id))["hints"]
    }
    assert by_candidate[stream_bug.id]["merge_effect"] == "returns_production"
    release_hints = {
        h["candidate"]["id"]: h
        for h in (await hints(rig["qa_client"], dup_of_release.id))["hints"]
    }
    assert release_hints[release_bug.id]["merge_effect"] == "returns_release_qa"

    # The merge does what the hint said (PRD AC-50: Stream → production).
    resp = await triage(
        rig["lead_client"], dup_of_stream.id,
        outcome="duplicate", duplicate_of_id=stream_bug.id,
    )
    assert resp.status_code == 200, resp.text
    after = (await rig["admin"].get(f"/issues/{stream_bug.id}")).json()
    assert after["status"] == "rejected" and after["reject_reason"] == "production"
    assert [c["start_reason"] for c in await factories.cycles(stream_bug.id)] == [
        "planned", "production",
    ]

    # …and AC-51: a Release that hasn't shipped → release QA.
    resp = await triage(
        rig["lead_client"], dup_of_release.id,
        outcome="duplicate", duplicate_of_id=release_bug.id,
    )
    assert resp.status_code == 200, resp.text
    after = (await rig["admin"].get(f"/issues/{release_bug.id}")).json()
    assert after["status"] == "rejected" and after["reject_reason"] == "release_qa"
    assert after["release_id"] == release.id
    assert [c["start_reason"] for c in await factories.cycles(release_bug.id)] == [
        "planned", "release_qa",
    ]


async def test_ac_s12_dismissed_pair_never_returns_after_reindex(
    factories, rig, reaction_world, jev, search_jobs,
):
    jev.default(judge_by_title)
    await enable_jev(factories.admin_client)
    new_bug = await factories.issue(project_id=rig["project"].id, title=REACTION_DRAFT)
    await search_jobs.run()
    candidate = reaction_world["report"]
    assert candidate.id in {
        h["candidate"]["id"] for h in (await hints(rig["qa_client"], new_bug.id))["hints"]
    }

    resp = await dismiss(rig["lead_client"], new_bug.id, candidate.id)
    assert resp.status_code == 204
    assert candidate.id not in {
        h["candidate"]["id"] for h in (await hints(rig["qa_client"], new_bug.id))["hints"]
    }

    # A full reindex…
    assert (await factories.admin_client.post("/settings/search/reindex")).status_code == 202
    await search_jobs.run()
    # …and a recomputation (the draft changed while New) both leave it gone.
    jev.calls.clear()
    resp = await rig["admin"].patch(f"/issues/{new_bug.id}", json={"title": REACTION_DRAFT + "!"})
    assert resp.status_code == 200, resp.text
    await search_jobs.run()
    assert any(k.startswith("c_") for c in jev.calls for k in c["questions"])  # judged again
    assert all(
        h["candidate"]["id"] != candidate.id
        for h in (await hints(rig["qa_client"], new_bug.id))["hints"]
    )


async def test_ac_s13_hint_hidden_after_leaving_new(
    factories, rig, reaction_world, jev, search_jobs,
):
    jev.default(judge_by_title)
    await enable_jev(factories.admin_client)
    new_bug = await factories.issue(project_id=rig["project"].id, title=REACTION_DRAFT)
    await search_jobs.run()
    assert (await hints(rig["qa_client"], new_bug.id))["hints"]

    resp = await triage(
        rig["lead_client"], new_bug.id, outcome="accept", priority="high",
    )
    assert resp.status_code == 200, resp.text
    assert (await hints(rig["qa_client"], new_bug.id))["hints"] == []
    row = await queue_row(rig["lead_client"], new_bug.id, rig["project"].id)
    assert row is None or row["possible_duplicates_count"] == 0


async def test_turning_jev_off_hides_and_on_restores_without_recomputation(
    factories, rig, reaction_world, jev, search_jobs,
):
    jev.default(judge_by_title)
    admin = factories.admin_client
    await enable_jev(admin)
    new_bug = await factories.issue(project_id=rig["project"].id, title=REACTION_DRAFT)
    await search_jobs.run()
    stored = (await hints(rig["qa_client"], new_bug.id))["hints"]
    assert stored

    await disable_jev(admin)
    assert (await hints(rig["qa_client"], new_bug.id))["hints"] == []
    row = await queue_row(rig["lead_client"], new_bug.id, rig["project"].id)
    assert row is not None and row["possible_duplicates_count"] == 0

    await enable_jev(admin)
    jev.calls.clear()
    assert (await hints(rig["qa_client"], new_bug.id))["hints"] == stored
    assert jev.calls == []  # shown from storage, not recomputed


async def test_hints_endpoints_are_tech_only(
    factories, rig, reaction_world, client_for, jev, search_jobs,
):
    jev.default(judge_by_title)
    await enable_jev(factories.admin_client)
    new_bug = await factories.issue(project_id=rig["project"].id, title=REACTION_DRAFT)
    await search_jobs.run()

    # A support-sourced item Support can see: 403, not 404 (FR-S13).
    resp = await rig["support_client"].get(f"/issues/{reaction_world['report'].id}/duplicate-hints")
    assert resp.status_code == 403
    # An internal item Support cannot see: 404 (04's rule).
    resp = await rig["support_client"].get(f"/issues/{new_bug.id}/duplicate-hints")
    assert resp.status_code == 404
    resp = await rig["support_client"].post(
        f"/issues/{new_bug.id}/duplicate-hints/{reaction_world['report'].id}/dismiss"
    )
    assert resp.status_code in (403, 404)


# ── AC-S14: cancelled is never suggested ─────────────────────────────────────


async def test_ac_s14_cancelled_never_suggested(
    factories, rig, reaction_world, jev, search_jobs,
):
    jev.default(judge_by_title)
    await enable_jev(factories.admin_client)
    cancelled = reaction_world["cancelled"]

    resp = await similar(rig["qa_client"], {
        "context": "tech", "project_id": rig["project"].id, "title": REACTION_VARIANT,
    })
    assert resp.status_code == 200, resp.text
    assert all(i["issue"]["id"] != cancelled.id for i in resp.json()["items"])

    new_bug = await factories.issue(project_id=rig["project"].id, title=REACTION_VARIANT)
    await search_jobs.run()
    assert all(
        h["candidate"]["id"] != cancelled.id
        for h in (await hints(rig["qa_client"], new_bug.id))["hints"]
    )


# ── Triggers ─────────────────────────────────────────────────────────────────


async def test_hint_recomputed_when_title_changes_while_new(
    factories, rig, reaction_world, jev, search_jobs,
):
    jev.default(judge_by_title)
    await enable_jev(factories.admin_client)
    new_bug = await factories.issue(project_id=rig["project"].id, title=PAYMENT_DRAFT)
    await search_jobs.run()
    assert (await hints(rig["qa_client"], new_bug.id))["hints"] == []

    # The draft moves onto the reactions problem: hints appear.
    resp = await rig["admin"].patch(f"/issues/{new_bug.id}", json={"title": REACTION_DRAFT})
    assert resp.status_code == 200, resp.text
    await search_jobs.run()
    assert (await hints(rig["qa_client"], new_bug.id))["hints"]


async def test_hint_computed_when_bug_reenters_new(
    factories, rig, reaction_world, jev, search_jobs,
):
    jev.default(judge_by_title)
    await enable_jev(factories.admin_client)
    new_bug = await factories.issue(project_id=rig["project"].id, title=REACTION_DRAFT)
    await search_jobs.run()
    assert (await hints(rig["qa_client"], new_bug.id))["hints"]

    # Needs info → the reporter answers → back in New: hints recomputed.
    await triage(rig["lead_client"], new_bug.id, outcome="needs_info", comment="Which chat?")
    assert (await hints(rig["qa_client"], new_bug.id))["hints"] == []
    resp = await rig["admin"].post(
        f"/issues/{new_bug.id}/timeline", json={"body": "گروه تسته"},
    )
    assert resp.status_code == 201, resp.text
    await search_jobs.run()
    assert (await hints(rig["qa_client"], new_bug.id))["hints"]
