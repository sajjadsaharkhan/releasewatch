"""Characterization: file (with a release) → triage → fix → verify → reopen.

Locks in today's Phase 1 issue lifecycle so slice 02 can prove it only
renamed statuses, not changed behavior (docs/phase-2/01-test-harness.md).
"""

import pytest


@pytest.mark.asyncio
async def test_file_triage_fix_verify_pass(factories, client_for, telegram):
    reporter = await factories.user(role="qa")
    developer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)

    reporter_client = await client_for(reporter)
    issue = await factories.issue(
        release_id=release.id, client=reporter_client, title="Login button does nothing"
    )
    assert issue.status == "new"
    assert issue.priority is None
    assert issue.release_id == release.id

    await telegram.link_telegram(developer)

    admin = factories.admin_client
    triage_resp = await admin.post(
        f"/issues/{issue.id}/triage",
        json={"outcome": "accept", "assignee_id": developer.id, "priority": "high"},
    )
    assert triage_resp.status_code == 200
    triaged = triage_resp.json()
    assert triaged["status"] == "todo"
    assert triaged["priority"] == "high"
    assert triaged["assignee_id"] == developer.id

    # Triaging assigns the developer — they get a Telegram notification.
    assert any(template == "assigned" for template, _ in telegram.sent_to(developer))

    dev_client = await client_for(developer)
    start_resp = await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    assert start_resp.status_code == 200

    fix_resp = await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": "https://example.com/mr/1"})
    assert fix_resp.status_code == 200
    assert fix_resp.json()["status"] == "in_review"

    qa_client = await client_for(reporter)
    verify_resp = await qa_client.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    assert verify_resp.status_code == 200
    verified = verify_resp.json()
    assert verified["status"] == "done"
    assert verified["verified_at"] is not None


@pytest.mark.asyncio
async def test_verify_fail_then_reopen(factories, client_for):
    developer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    admin = factories.admin_client
    dev_client = await client_for(developer)
    await admin.post(
        f"/issues/{issue.id}/triage",
        json={"outcome": "accept", "assignee_id": developer.id, "priority": "critical"},
    )
    await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})

    # 09a: a failed verification is refused — Reject is its own action, and
    # there's no self-verification rule, so the developer can reject their own fix.
    verify_resp = await dev_client.post(
        f"/issues/{issue.id}/verify", json={"outcome": "fail", "note": "Still crashes"},
    )
    assert verify_resp.status_code == 409
    assert verify_resp.json()["code"] == "use_reject"
    reject_resp = await dev_client.post(
        f"/issues/{issue.id}/reject", json={"comment": "Still crashes"},
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    # Fix again, then verify pass from a different actor (AC-27: reviewer
    # can't verify their own fix), then reopen from done.
    # reopen is an alias of Reject for Done items (09a; the release hasn't shipped → release QA).
    await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})
    verify_ok = await admin.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    assert verify_ok.json()["status"] == "done"

    reopen_resp = await admin.post(f"/issues/{issue.id}/reopen", json={"comment": "Back again"})
    assert reopen_resp.status_code == 200
    reopened = reopen_resp.json()
    assert reopened["status"] == "rejected"
    assert reopened["verified_at"] is None
    # The reject from review and the return from release QA are both cycles
    # Phase 1 reports count (08a).
    assert await factories.regression_count(issue.id) == 2


@pytest.mark.asyncio
async def test_cannot_triage_twice(factories):
    developer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    admin = factories.admin_client
    first = await admin.post(
        f"/issues/{issue.id}/triage",
        json={"outcome": "accept", "assignee_id": developer.id, "priority": "medium"},
    )
    assert first.status_code == 200

    second = await admin.post(
        f"/issues/{issue.id}/triage",
        json={"outcome": "accept", "assignee_id": developer.id, "priority": "medium"},
    )
    assert second.status_code == 409
    body = second.json()
    assert "triage" in body["detail"].lower()
