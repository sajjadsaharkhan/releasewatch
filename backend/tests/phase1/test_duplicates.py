"""Characterization: marking one issue a duplicate of another.

Slice 06 replaced Phase 1's ``POST /issues/{id}/duplicate`` with the
Duplicate triage outcome (a merge — see tests/phase2/test_triage_outcomes.py).
The Phase 1 behavior these lock in still holds through it.
"""

import pytest


@pytest.mark.asyncio
async def test_link_duplicate_closes_child_and_sets_parent(factories):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    parent = await factories.issue(release_id=release.id, title="Crash on save")
    child = await factories.issue(release_id=release.id, title="App crashes when saving")

    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{child.id}/triage", json={"outcome": "duplicate", "duplicate_of_id": parent.id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancel_reason"] == "duplicate"
    assert body["parent_issue_id"] == parent.id

    # The parent keeps its status (it's New — BR-49).
    parent_resp = await admin.get(f"/issues/{parent.id}")
    assert parent_resp.json()["status"] == "new"


@pytest.mark.asyncio
async def test_cannot_duplicate_self(factories):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/triage", json={"outcome": "duplicate", "duplicate_of_id": issue.id},
    )
    assert resp.status_code == 409
    assert resp.json()["code"] == "duplicate_of_self"
