"""Coverage for status-derived counts that had no Phase 1 test.

``GET /releases/{id}`` (open_issues/blocker_count/fixed_issues,
``app/api/v1/releases.py::_add_release_metrics``) and the user profile's
fixed/fix_rate (``app/api/v1/users.py::_FIXED_STATUSES``) both read
``Issue.status`` directly and were updated for the unified status model
(docs/phase-2/02-unified-status-model.md), but neither had a characterization
test in ``tests/phase1/`` — that suite only covers
``GET /reports/releases/{id}`` (a different endpoint, ``ReportService``).
"""

import pytest


@pytest.mark.asyncio
async def test_release_metrics_count_by_new_statuses(factories, client_for):
    developer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    admin = factories.admin_client
    dev_client = await client_for(developer)

    # One new, one todo+blocker, one in_review, one done.
    await factories.issue(release_id=release.id)
    blocker = await factories.issue(release_id=release.id, is_release_blocker=True)
    to_review = await factories.issue(release_id=release.id)
    to_done = await factories.issue(release_id=release.id)

    await admin.patch(f"/issues/{blocker.id}", json={"is_release_blocker": True})
    await admin.post(
        f"/issues/{blocker.id}/triage",
        json={"outcome": "accept", "assignee_id": developer.id, "priority": "critical"},
    )
    for issue in (to_review, to_done):
        await admin.post(
            f"/issues/{issue.id}/triage",
            json={"outcome": "accept", "assignee_id": developer.id, "priority": "high"},
        )
        await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
        await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})
    await admin.post(f"/issues/{to_done.id}/verify", json={"outcome": "pass"})

    resp = await admin.get(f"/releases/{release.id}")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_issues"] == 4
    assert body["blocker_count"] == 1
    # open = not done and not cancelled: new, todo+blocker, in_review.
    assert body["open_issues"] == 3
    # fixed = in_review or done: to_review and to_done.
    assert body["fixed_issues"] == 2


@pytest.mark.asyncio
async def test_user_profile_fixed_count_uses_in_review_and_done(factories, client_for):
    developer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    admin = factories.admin_client
    dev_client = await client_for(developer)

    # Assigned but still in_progress — not counted as fixed.
    in_progress_issue = await factories.issue(release_id=release.id)
    # Assigned and moved to in_review — counted as fixed.
    in_review_issue = await factories.issue(release_id=release.id)
    # Assigned and verified to done — counted as fixed.
    done_issue = await factories.issue(release_id=release.id)

    for issue in (in_progress_issue, in_review_issue, done_issue):
        await admin.post(
            f"/issues/{issue.id}/triage",
            json={"outcome": "accept", "assignee_id": developer.id, "priority": "medium"},
        )
        await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})

    for issue in (in_review_issue, done_issue):
        await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})
    await admin.post(f"/issues/{done_issue.id}/verify", json={"outcome": "pass"})

    resp = await admin.get(f"/users/by-username/{developer.username}")
    assert resp.status_code == 200
    body = resp.json()

    assert body["fixed"] == 2
    assert body["fixRate"] == pytest.approx(round(2 / 3 * 100))
