"""Characterization: comments on an issue's timeline.

Today (Phase 1), ``GET /issues/{id}/timeline`` always calls
``timeline_service.list_timeline(..., include_internal=True)`` — there is no
query param wired up to filter internal notes out, so every authenticated
caller currently sees internal comments too. This is the "before" state
slice 06 (which wires real visibility for support/external roles) diffs
against.
"""

import pytest


@pytest.mark.asyncio
async def test_comment_round_trips_on_timeline(factories, client_for):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/timeline",
        json={"body": "Can reproduce on staging.", "is_internal": False},
    )
    assert resp.status_code == 201
    assert resp.json()["is_internal"] is False

    timeline = await admin.get(f"/issues/{issue.id}/timeline")
    bodies = [e["body"] for e in timeline.json()["items"]]
    assert "Can reproduce on staging." in bodies


@pytest.mark.asyncio
async def test_internal_comment_visible_to_other_tech_users(factories, client_for):
    """Internal notes are for every tech role (BR-31); Support's view is covered in
    tests/phase2/test_roles_and_visibility.py (slice 04 closed the old gap)."""
    other_qa = await factories.user(role="qa")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    admin = factories.admin_client
    resp = await admin.post(
        f"/issues/{issue.id}/timeline",
        json={"body": "Internal: this is a flaky test, not a real bug.", "is_internal": True},
    )
    assert resp.status_code == 201

    other_client = await client_for(other_qa)
    timeline = await other_client.get(f"/issues/{issue.id}/timeline")
    bodies = [e["body"] for e in timeline.json()["items"]]
    assert "Internal: this is a flaky test, not a real bug." in bodies
