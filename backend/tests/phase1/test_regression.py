"""Characterization: regression recording and regression_count (read from cycles, 08a).

08a replaces the regression action with returns: ``POST /issues/{id}/returns``
sends Done work back (``release_qa`` while its release hasn't shipped).
"""

import pytest


@pytest.mark.asyncio
async def test_regression_increments_count_and_records_history(factories, client_for):
    developer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    admin = factories.admin_client
    dev_client = await client_for(developer)
    await admin.post(
        f"/issues/{issue.id}/triage",
        json={"outcome": "accept", "assignee_id": developer.id, "priority": "high"},
    )
    await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})
    # AC-27: the developer who moved it to review can't verify their own fix.
    verify_resp = await admin.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    assert verify_resp.json()["status"] == "done"

    regress_resp = await admin.post(f"/issues/{issue.id}/returns", json={"comment": "Broke again"})
    assert regress_resp.status_code == 200
    regressed = regress_resp.json()
    assert regressed["status"] == "rejected"
    assert await factories.regression_count(issue.id) == 1

    history = [c for c in await factories.cycles(issue.id) if c["start_reason"] != "planned"]
    assert len(history) == 1
    assert history[0]["cycle_number"] == 2
    assert history[0]["release_id"] == release.id

    # A second regression on the same issue increments again.
    await dev_client.post(f"/issues/{issue.id}/transition", json={"to": "in_progress"})
    await dev_client.post(f"/issues/{issue.id}/fix", json={"mr_url": None})
    await admin.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    second = await admin.post(f"/issues/{issue.id}/returns", json={"comment": "And again"})
    assert second.status_code == 200
    assert await factories.regression_count(issue.id) == 2
