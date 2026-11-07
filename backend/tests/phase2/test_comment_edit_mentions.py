"""BUG-900: mentions added while editing a comment must persist."""

import pytest


@pytest.mark.asyncio
async def test_edit_persists_mentions(factories):
    project = await factories.project()
    release = await factories.release(project_id=project.id)
    bug = await factories.issue(project_id=project.id, release_id=release.id)
    other = await factories.user(role="qa")
    c = factories.admin_client

    posted = await c.post(f"/issues/{bug.id}/timeline", json={"body": "hello"})
    event_id = posted.json()["id"]
    assert posted.json()["mentioned_user_ids"] == []

    edited = await c.patch(
        f"/issues/{bug.id}/timeline/{event_id}",
        json={"body": "hello @x", "mentioned_user_ids": [other.id]},
    )
    assert edited.status_code == 200
    assert edited.json()["mentioned_user_ids"] == [other.id]

    items = (await c.get(f"/issues/{bug.id}/timeline")).json()["items"]
    stored = next(i for i in items if i["id"] == event_id)
    assert stored["mentioned_user_ids"] == [other.id]

    # Omitting the field leaves mentions untouched.
    again = await c.patch(f"/issues/{bug.id}/timeline/{event_id}", json={"body": "hello @x!"})
    assert again.json()["mentioned_user_ids"] == [other.id]
