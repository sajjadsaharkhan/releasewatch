"""Who may delete an item: the CTO, admins, the project's triage lead — and
whoever filed it, whatever their role (2026-10-14: the frontend hid Delete
from reporters because it compared a string user id with a numeric one)."""

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["developer", "qa", "product_manager"])
async def test_the_reporter_can_delete_what_they_filed(factories, client_for, role):
    project = await factories.project()
    reporter = await factories.user(role=role)
    client = await client_for(reporter)
    bug = await factories.issue(project_id=project.id, client=client)

    assert (await client.delete(f"/issues/{bug.id}")).status_code == 204
    assert (await client.get(f"/issues/{bug.id}")).status_code == 404


@pytest.mark.asyncio
async def test_someone_elses_item_cannot_be_deleted(factories, client_for):
    project = await factories.project()
    reporter, other = await factories.user(role="qa"), await factories.user(role="developer")
    bug = await factories.issue(project_id=project.id, client=await client_for(reporter))

    resp = await (await client_for(other)).delete(f"/issues/{bug.id}")
    assert resp.status_code == 403
    assert (await factories.admin_client.get(f"/issues/{bug.id}")).status_code == 200


@pytest.mark.asyncio
async def test_the_issue_carries_the_reporter_id_the_delete_check_needs(factories, client_for):
    project = await factories.project()
    reporter = await factories.user(role="qa")
    client = await client_for(reporter)
    bug = await factories.issue(project_id=project.id, client=client)

    me = (await client.get("/auth/me")).json()
    issue = (await client.get(f"/issues/{bug.id}")).json()
    assert str(issue["reporter_id"]) == str(me["id"])
