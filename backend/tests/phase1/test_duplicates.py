"""Characterization: linking one issue as a duplicate of another."""

import pytest


@pytest.mark.asyncio
async def test_link_duplicate_closes_child_and_sets_parent(factories):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    parent = await factories.issue(release_id=release.id, title="Crash on save")
    child = await factories.issue(release_id=release.id, title="App crashes when saving")

    admin = factories.admin_client
    resp = await admin.post(f"/issues/{child.id}/duplicate", json={"parent_id": parent.id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "closed"
    assert body["parent_issue_id"] == parent.id

    # The parent itself is untouched.
    parent_resp = await admin.get(f"/issues/{parent.id}")
    assert parent_resp.json()["status"] == "new"


@pytest.mark.asyncio
async def test_cannot_duplicate_self(factories):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    admin = factories.admin_client
    resp = await admin.post(f"/issues/{issue.id}/duplicate", json={"parent_id": issue.id})
    assert resp.status_code == 400
