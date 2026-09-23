"""Characterization: GET /reports/releases/{id} counts for a known fixture."""

import pytest


@pytest.mark.asyncio
async def test_release_report_counts(factories, client_for):
    developer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    admin = factories.admin_client
    dev_client = await client_for(developer)

    # One new, one triaged(todo)+blocker, one in_review, one done.
    await factories.issue(release_id=release.id, priority="medium")
    blocker = await factories.issue(
        release_id=release.id, priority="critical", is_release_blocker=True
    )
    to_fix = await factories.issue(release_id=release.id, priority="high")
    to_verify = await factories.issue(release_id=release.id, priority="critical")

    await admin.post(
        f"/issues/{blocker.id}/triage",
        json={"assignee_id": developer.id, "priority": "critical", "is_release_blocker": True},
    )

    for issue in (to_fix, to_verify):
        await admin.post(
            f"/issues/{issue.id}/triage",
            json={"assignee_id": developer.id, "priority": issue.priority},
        )
        await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
        await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})
    # AC-27: the developer who moved it to review can't verify their own fix.
    await admin.post(f"/issues/{to_verify.id}/verify", json={"outcome": "pass"})

    report_resp = await admin.get(f"/reports/releases/{release.id}")
    assert report_resp.status_code == 200
    report = report_resp.json()

    assert report["total_issues"] == 4
    assert report["blocker_count"] == 1
    # open = not done and not cancelled: the new issue, the todo blocker, and
    # the in_review bug; the done bug doesn't count.
    assert report["open_issues"] == 3
    assert report["status_breakdown"]["new"] == 1
    assert report["status_breakdown"]["todo"] == 1
    assert report["status_breakdown"]["in_review"] == 1
    assert report["status_breakdown"]["done"] == 1
    # Phase 1's blocker and critical both land on critical (03a mapping).
    assert report["priority_breakdown"]["critical"] == 2
    assert report["priority_breakdown"]["high"] == 1
    assert report["priority_breakdown"]["medium"] == 1
    assert report["priority_breakdown"]["low"] == 0
