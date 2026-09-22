"""Characterization: @mention → inbox fan-out.

Rewrite of the old manual script (``backend/scripts/test_mention_inbox.py``,
deleted in this slice) as a real pytest test, covering both the explicit
``mentioned_user_ids`` path and the ``@username`` regex-fallback path in
``POST /issues/{id}/timeline`` (app/api/v1/timeline.py::create_comment).
"""

import pytest


@pytest.mark.asyncio
async def test_explicit_mentioned_user_ids_creates_one_inbox_item(factories, client_for):
    actor = await factories.user(role="developer")
    mentioned = await factories.user(role="qa")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    actor_client = await client_for(actor)
    resp = await actor_client.post(
        f"/issues/{issue.id}/timeline",
        json={
            "body": f"hey @{mentioned.username}",
            "is_internal": False,
            "mentioned_user_ids": [mentioned.id],
        },
    )
    assert resp.status_code == 201

    mentioned_client = await client_for(mentioned)
    inbox = await mentioned_client.get("/inbox", params={"event_type": "mention"})
    items = inbox.json()["items"]
    assert len(items) == 1
    assert items[0]["issueId"] == f"issue-{issue.issue_number}"


@pytest.mark.asyncio
async def test_regex_fallback_mention_creates_one_inbox_item(factories, client_for):
    actor = await factories.user(role="developer")
    mentioned = await factories.user(role="qa")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    actor_client = await client_for(actor)
    resp = await actor_client.post(
        f"/issues/{issue.id}/timeline",
        json={
            "body": f"hey @{mentioned.username} what do you think?",
            "is_internal": False,
            "mentioned_user_ids": [],
        },
    )
    assert resp.status_code == 201

    mentioned_client = await client_for(mentioned)
    inbox = await mentioned_client.get("/inbox", params={"event_type": "mention"})
    assert len(inbox.json()["items"]) == 1


@pytest.mark.asyncio
async def test_actor_is_not_notified_of_their_own_mention(factories, client_for):
    actor = await factories.user(role="developer")
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    issue = await factories.issue(release_id=release.id)

    actor_client = await client_for(actor)
    await actor_client.post(
        f"/issues/{issue.id}/timeline",
        json={
            "body": f"note to self @{actor.username}",
            "is_internal": False,
            "mentioned_user_ids": [actor.id],
        },
    )

    inbox = await actor_client.get("/inbox", params={"event_type": "mention"})
    assert inbox.json()["items"] == []
