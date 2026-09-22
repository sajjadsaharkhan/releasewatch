"""Workflow — table-driven transition tests, tested only through the API.

One test per allowed path in docs/phase-2/02-unified-status-model.md's
Workflow table, plus one test that the nearest disallowed target 409s with
the right ``code`` and ``allowed`` list. Named AC tests cover AC-25/26/27.
"""

import pytest


async def _new_bug(factories, release_id, **overrides):
    return await factories.issue(release_id=release_id, **overrides)


async def _todo_bug(factories, client_for, release_id, developer):
    """A bug triaged to todo, assigned to ``developer``."""
    issue = await _new_bug(factories, release_id)
    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/triage",
        json={"assignee_id": developer.id, "severity": "major"},
    )
    assert resp.status_code == 200
    return issue


async def _in_progress_bug(factories, client_for, release_id, developer):
    issue = await _todo_bug(factories, client_for, release_id, developer)
    dev_client = await client_for(developer)
    resp = await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    assert resp.status_code == 200
    return issue


async def _in_review_bug(factories, client_for, release_id, developer):
    issue = await _in_progress_bug(factories, client_for, release_id, developer)
    dev_client = await client_for(developer)
    resp = await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})
    assert resp.status_code == 200
    return issue


async def _done_bug(factories, client_for, release_id, developer, verifier_client):
    issue = await _in_review_bug(factories, client_for, release_id, developer)
    resp = await verifier_client.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"
    return issue


@pytest.fixture
async def rig(factories):
    developer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    return {"developer": developer, "project": project, "release": release}


# ── new -> todo / needs_info: only via the triage outcome ───────────────────


@pytest.mark.asyncio
async def test_new_to_todo_only_via_triage(factories, client_for, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client

    direct = await admin.post(f"/issues/{issue.id}/transition", json={"to": "todo"})
    assert direct.status_code == 409
    assert direct.json()["code"] == "invalid_transition"

    via_triage = await admin.post(
        f"/issues/{issue.id}/triage",
        json={"assignee_id": rig["developer"].id, "severity": "minor"},
    )
    assert via_triage.status_code == 200
    assert via_triage.json()["status"] == "todo"


@pytest.mark.asyncio
async def test_new_to_needs_info_only_via_triage_outcome(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client

    direct = await admin.post(f"/issues/{issue.id}/transition", json={"to": "needs_info"})
    assert direct.status_code == 409
    assert direct.json()["code"] == "invalid_transition"

    via_outcome = await admin.post(
        f"/issues/{issue.id}/needs-clarification", json={"message": "repro?"},
    )
    assert via_outcome.status_code == 200
    assert via_outcome.json()["status"] == "needs_info"


# ── cancel: new, todo, needs_info, blocked -> cancelled, reason required ────


@pytest.mark.asyncio
async def test_cancel_requires_reason(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client

    no_reason = await admin.post(f"/issues/{issue.id}/transition", json={"to": "cancelled"})
    assert no_reason.status_code == 409
    assert no_reason.json()["code"] == "cancel_reason_required"

    with_reason = await admin.post(
        f"/issues/{issue.id}/transition",
        json={"to": "cancelled", "cancel_reason": "wont_fix"},
    )
    assert with_reason.status_code == 200
    body = with_reason.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "wont_fix"
    assert body["cancelled_at"] is not None


@pytest.mark.asyncio
async def test_cancel_allowed_from_todo_needs_info_and_blocked(factories, client_for, rig):
    admin = factories.admin_client

    todo_issue = await _todo_bug(factories, client_for, rig["release"].id, rig["developer"])
    resp = await admin.post(
        f"/issues/{todo_issue.id}/transition",
        json={"to": "cancelled", "cancel_reason": "user_error"},
    )
    assert resp.status_code == 200

    needs_info_issue = await _new_bug(factories, rig["release"].id)
    await admin.post(f"/issues/{needs_info_issue.id}/needs-clarification", json={})
    resp = await admin.post(
        f"/issues/{needs_info_issue.id}/transition",
        json={"to": "cancelled", "cancel_reason": "cannot_reproduce"},
    )
    assert resp.status_code == 200

    blocked_issue = await _todo_bug(factories, client_for, rig["release"].id, rig["developer"])
    await admin.post(f"/issues/{blocked_issue.id}/transition", json={"to": "blocked"})
    resp = await admin.post(
        f"/issues/{blocked_issue.id}/transition",
        json={"to": "cancelled", "cancel_reason": "duplicate"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cancel_not_allowed_from_in_progress(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/transition",
        json={"to": "cancelled", "cancel_reason": "wont_fix"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_transition"
    assert "cancelled" not in resp.json()["allowed"]


# ── needs_info -> new ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_needs_info_to_new(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client
    await admin.post(f"/issues/{issue.id}/needs-clarification", json={})

    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "new"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "new"


@pytest.mark.asyncio
async def test_new_to_new_is_refused(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "new"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_transition"


# ── todo -> in_progress ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_todo_to_in_progress(factories, client_for, rig):
    issue = await _todo_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["started_at"] is not None


@pytest.mark.asyncio
async def test_todo_to_done_is_refused(factories, client_for, rig):
    issue = await _todo_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "done"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_transition"
    assert set(resp.json()["allowed"]) == {"in_progress", "blocked", "cancelled"}


# ── in_progress -> in_review ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_in_progress_to_in_review_records_reviewer(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    dev_client = await client_for(rig["developer"])
    resp = await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_review"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_review"
    assert body["review_requested_by_id"] == rig["developer"].id
    assert body["fixed_at"] is not None


@pytest.mark.asyncio
async def test_in_progress_to_cancelled_is_refused(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/transition", json={"to": "cancelled", "cancel_reason": "wont_fix"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_transition"


# ── in_review -> done (verify pass) / in_progress (verify fail) ─────────────


@pytest.mark.asyncio
async def test_in_review_to_done_verify_pass(factories, client_for, rig):
    issue = await _in_review_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "done"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "done"
    assert body["completed_at"] is not None


@pytest.mark.asyncio
async def test_in_review_to_in_progress_verify_fail(factories, client_for, rig):
    issue = await _in_review_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["review_requested_by_id"] is None


# ── AC-27: reviewer cannot verify their own fix ──────────────────────────────


@pytest.mark.asyncio
async def test_ac_27_reviewer_cannot_verify_own_fix(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    dev_client = await client_for(rig["developer"])
    await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})

    self_verify = await dev_client.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    assert self_verify.status_code == 409
    assert self_verify.json()["code"] == "self_verification"

    # A different actor can.
    admin = factories.admin_client
    other_verify = await admin.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    assert other_verify.status_code == 200
    assert other_verify.json()["status"] == "done"


@pytest.mark.asyncio
async def test_self_verification_surfaced_in_blocked_transitions(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    dev_client = await client_for(rig["developer"])
    await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})

    detail_resp = await dev_client.get(f"/issues/{issue.id}")
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    blocked = {b["to"]: b for b in body["blocked_transitions"]}
    assert blocked["done"]["code"] == "self_verification"
    assert "done" not in body["allowed_transitions"]


# ── blocked: from todo/in_progress/in_review, and back ──────────────────────


@pytest.mark.asyncio
async def test_block_and_unblock_returns_to_recorded_status(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client

    block_resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "blocked"})
    assert block_resp.status_code == 200
    body = block_resp.json()
    assert body["status"] == "blocked"
    assert body["blocked_from_status"] == "in_progress"

    unblock_resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    assert unblock_resp.status_code == 200
    unblocked = unblock_resp.json()
    assert unblocked["status"] == "in_progress"
    assert unblocked["blocked_from_status"] is None


@pytest.mark.asyncio
async def test_blocked_can_always_return_to_todo(factories, client_for, rig):
    issue = await _in_review_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    await admin.post(f"/issues/{issue.id}/transition", json={"to": "blocked"})

    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "todo"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "todo"


@pytest.mark.asyncio
async def test_blocked_to_done_is_refused(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    await admin.post(f"/issues/{issue.id}/transition", json={"to": "blocked"})

    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "done"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_transition"


# ── done -> in_progress: regression action only ──────────────────────────────


@pytest.mark.asyncio
async def test_done_to_in_progress_direct_transition_is_refused(factories, client_for, rig):
    admin = factories.admin_client
    issue = await _done_bug(factories, client_for, rig["release"].id, rig["developer"], admin)

    resp = await admin.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_transition"


@pytest.mark.asyncio
async def test_done_to_in_progress_merge_regression_reserved(factories, client_for, rig):
    """v2.1: the merge_regression row is reserved but unreachable — refused, code use_triage."""
    admin = factories.admin_client
    issue = await _done_bug(factories, client_for, rig["release"].id, rig["developer"], admin)

    resp = await admin.post(
        f"/issues/{issue.id}/transition",
        json={"to": "in_progress", "reason": "merge_regression"},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "use_triage"


@pytest.mark.asyncio
async def test_ac_25_regression_on_done_bug_in_unshipped_release(factories, client_for, rig):
    admin = factories.admin_client
    issue = await _done_bug(factories, client_for, rig["release"].id, rig["developer"], admin)

    resp = await admin.post(f"/issues/{issue.id}/regression")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["is_regression"] is True
    assert body["regression_count"] == 1
    assert body["verified_at"] is None
    assert body["completed_at"] is None

    history = await admin.get(f"/issues/{issue.id}/regressions")
    assert len(history.json()) == 1


@pytest.mark.asyncio
async def test_ac_25_regression_from_in_review(factories, client_for, rig):
    """The regression action also reaches from In review, not only Done."""
    issue = await _in_review_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/regression")
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"
    assert resp.json()["regression_count"] == 1


@pytest.mark.asyncio
async def test_ac_26_regression_unavailable_on_shipped_release(factories, client_for, rig):
    admin = factories.admin_client
    issue = await _done_bug(factories, client_for, rig["release"].id, rig["developer"], admin)

    await admin.patch(f"/releases/{rig['release'].id}", json={"status": "released"})

    resp = await admin.post(f"/issues/{issue.id}/regression")
    assert resp.status_code == 409
    assert resp.json()["code"] == "release_shipped"


@pytest.mark.asyncio
@pytest.mark.skip(reason="needs slice 03: release_id is NOT NULL until then (D7)")
async def test_ac_26_regression_unavailable_without_release(factories, client_for, rig):
    """A bug with no release can't have a regression recorded against it."""
    raise NotImplementedError


@pytest.mark.asyncio
@pytest.mark.skip(reason="needs slice 03: release_id is NOT NULL until then (D7)")
async def test_direct_regression_never_writes_history_without_release(factories, client_for, rig):
    """RegressionService.record_regression is only reachable with a release (BR-25)."""
    raise NotImplementedError


@pytest.mark.asyncio
async def test_regression_action_refused_from_in_progress(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client

    resp = await admin.post(f"/issues/{issue.id}/regression")
    assert resp.status_code == 409
    assert resp.json()["code"] == "invalid_transition"


# ── reopen maps to the regression action ─────────────────────────────────────


@pytest.mark.asyncio
async def test_reopen_maps_to_regression_action(factories, client_for, rig):
    admin = factories.admin_client
    issue = await _done_bug(factories, client_for, rig["release"].id, rig["developer"], admin)

    resp = await admin.post(f"/issues/{issue.id}/reopen")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "in_progress"
    assert body["is_regression"] is True


@pytest.mark.asyncio
async def test_reopen_refuses_non_done_bug(factories, client_for, rig):
    issue = await _in_progress_bug(factories, client_for, rig["release"].id, rig["developer"])
    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/reopen")
    assert resp.status_code == 409
    assert resp.json()["code"] == "done_is_final"


@pytest.mark.asyncio
async def test_reopen_refuses_done_bug_on_shipped_release(factories, client_for, rig):
    admin = factories.admin_client
    issue = await _done_bug(factories, client_for, rig["release"].id, rig["developer"], admin)
    await admin.patch(f"/releases/{rig['release'].id}", json={"status": "released"})

    resp = await admin.post(f"/issues/{issue.id}/reopen")
    assert resp.status_code == 409
    assert resp.json()["code"] == "done_is_final"


# ── PATCH obeys the same rules (D8 regression test) ──────────────────────────


@pytest.mark.asyncio
async def test_patch_status_obeys_workflow(factories, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client

    bad = await admin.patch(f"/issues/{issue.id}", json={"status": "todo"})
    assert bad.status_code == 409
    assert bad.json()["code"] == "invalid_transition"

    ok = await admin.patch(
        f"/issues/{issue.id}", json={"status": "cancelled", "cancel_reason": "wont_fix"},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "cancelled"
    assert ok.json()["cancel_reason"] == "wont_fix"


# ── Timeline records every status change (user story 24) ─────────────────────


@pytest.mark.asyncio
async def test_timeline_records_every_status_change(factories, client_for, rig):
    issue = await _new_bug(factories, rig["release"].id)
    admin = factories.admin_client

    await admin.post(
        f"/issues/{issue.id}/transition",
        json={"to": "cancelled", "cancel_reason": "wont_fix", "reason": "no longer needed"},
    )

    resp = await admin.get(f"/issues/{issue.id}/timeline")
    assert resp.status_code == 200
    events = [e for e in resp.json()["items"] if e["event_type"] == "status_changed"]
    assert len(events) == 1
    event = events[0]
    assert event["meta"]["from"] == "new"
    assert event["meta"]["to"] == "cancelled"
    assert event["meta"]["reason"] == "wont_fix"
    assert event["actor_id"] is not None
    assert event["actor_user"]["id"] == event["actor_id"]
