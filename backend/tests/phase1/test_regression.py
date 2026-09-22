"""Characterization: regression recording and regression_count.

Today (Phase 1), ``PATCH /issues/{id}`` accepts any ``status`` value directly
— there is no Workflow module yet to reject an invalid transition (that
lands in slice 02, docs/phase-2/00-README.md → D8). Setting ``status:
"regression"`` on a previously fixed/verified issue is how a regression is
recorded today.
"""

import pytest


@pytest.mark.asyncio
async def test_regression_increments_count_and_records_history(factories):
    developer = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    admin = factories.admin_client
    await admin.post(
        f"/issues/{issue.id}/triage",
        json={"assignee_id": developer.id, "severity": "major"},
    )
    await admin.post(f"/issues/{issue.id}/fix", json={"mr_url": None})
    verify_resp = await admin.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    assert verify_resp.json()["status"] == "verified"

    regress_resp = await admin.patch(f"/issues/{issue.id}", json={"status": "regression"})
    assert regress_resp.status_code == 200
    regressed = regress_resp.json()
    assert regressed["status"] == "regression"
    assert regressed["is_regression"] is True
    assert regressed["regression_count"] == 1

    history_resp = await admin.get(f"/issues/{issue.id}/regressions")
    assert history_resp.status_code == 200
    history = history_resp.json()
    assert len(history) == 1
    assert history[0]["regression_number"] == 1
    assert history[0]["release_id"] == release.id

    # A second regression on the same issue increments again.
    await admin.post(f"/issues/{issue.id}/fix", json={"mr_url": None})
    await admin.post(f"/issues/{issue.id}/verify", json={"outcome": "pass"})
    second = await admin.patch(f"/issues/{issue.id}", json={"status": "regression"})
    assert second.json()["regression_count"] == 2

    history_resp_2 = await admin.get(f"/issues/{issue.id}/regressions")
    assert len(history_resp_2.json()) == 2
