"""Subscribe button — any user can track an item; every change is on the timeline.

Observed through HTTP responses, each user's ``GET /inbox`` and the Telegram
recorder. The matrix's Subscriber column decides which events a subscriber hears.
"""

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def rig(factories, client_for):
    developer = await factories.user(role="developer")
    qa = await factories.user(role="qa")
    support = await factories.user(role="support")
    project = await factories.project()
    issue = await factories.issue(project_id=project.id)
    return {
        "admin": factories.admin_client,
        "qa": qa, "qa_client": await client_for(qa),
        "developer": developer, "dev_client": await client_for(developer),
        "support": support, "support_client": await client_for(support),
        "issue": issue,
    }


async def inbox_types(client) -> list[str]:
    return [i["type"] for i in (await client.get("/inbox", params={"size": 100})).json()["items"]]


async def sub_events(client, issue_id) -> list[str]:
    items = (await client.get(f"/issues/{issue_id}/timeline", params={"size": 200})).json()["items"]
    return [e["event_type"] for e in items if e["event_type"] in ("subscribed", "unsubscribed")]


@pytest.mark.asyncio
async def test_subscribe_and_unsubscribe_are_idempotent_and_recorded(rig):
    client, issue_id = rig["qa_client"], rig["issue"].id
    before = (await client.get(f"/issues/{issue_id}")).json()
    assert before["is_subscribed"] is False

    first = (await client.put(f"/issues/{issue_id}/subscription")).json()
    again = (await client.put(f"/issues/{issue_id}/subscription")).json()
    assert first["is_subscribed"] and again["is_subscribed"]
    assert again["subscriber_count"] == before["subscriber_count"] + 1
    assert await sub_events(client, issue_id) == ["subscribed"]  # one entry, not two

    gone = (await client.delete(f"/issues/{issue_id}/subscription")).json()
    await client.delete(f"/issues/{issue_id}/subscription")
    assert gone["is_subscribed"] is False
    assert gone["subscriber_count"] == before["subscriber_count"]
    assert await sub_events(client, issue_id) == ["subscribed", "unsubscribed"]
    # Everyone sees it on the timeline, and the actor is recorded.
    items = (await rig["admin"].get(f"/issues/{issue_id}/timeline", params={"size": 200})).json()["items"]
    assert any(e["event_type"] == "subscribed" and e["actor_id"] == rig["qa"].id for e in items)


@pytest.mark.asyncio
async def test_subscriber_list_names_who_and_why(rig):
    issue_id = rig["issue"].id
    await rig["qa_client"].put(f"/issues/{issue_id}/subscription")
    listed = (await rig["dev_client"].get(f"/issues/{issue_id}/subscribers")).json()
    assert [(s["user"]["id"], s["reason"]) for s in listed][-1] == (rig["qa"].id, "manual")
    assert (await rig["support_client"].get(f"/issues/{issue_id}/subscribers")).status_code == 404


@pytest.mark.asyncio
async def test_reporter_can_unsubscribe(factories, client_for):
    reporter = await factories.user(role="qa")
    client = await client_for(reporter)
    issue = await factories.issue(client=client)
    assert (await client.get(f"/issues/{issue.id}")).json()["is_subscribed"] is True
    resp = (await client.delete(f"/issues/{issue.id}/subscription")).json()
    assert resp["is_subscribed"] is False


@pytest.mark.asyncio
async def test_subscriber_hears_events_the_matrix_enables(factories, rig, telegram):
    issue_id = rig["issue"].id
    await rig["dev_client"].put(f"/issues/{issue_id}/subscription")
    await telegram.link_telegram(rig["developer"])

    # Off by default: a comment reaches the developer nowhere.
    await rig["admin"].post(f"/issues/{issue_id}/timeline", json={"body": "first"})
    assert "comment" not in await inbox_types(rig["dev_client"])

    await rig["admin"].put("/settings/notifications", json={"comment": {"subscriber": True}})
    await rig["admin"].post(f"/issues/{issue_id}/timeline", json={"body": "second"})
    assert (await inbox_types(rig["dev_client"])).count("comment") == 1
    assert len(telegram.sent_to(rig["developer"])) == 1

    # After unsubscribing, nothing more arrives.
    await rig["dev_client"].delete(f"/issues/{issue_id}/subscription")
    await rig["admin"].post(f"/issues/{issue_id}/timeline", json={"body": "third"})
    assert (await inbox_types(rig["dev_client"])).count("comment") == 1


@pytest.mark.asyncio
async def test_support_cannot_subscribe_to_an_item_it_cannot_see(rig):
    # Support sees only its own reports, so another item is a 404 — the same wall as everywhere else.
    resp = await rig["support_client"].put(f"/issues/{rig['issue'].id}/subscription")
    assert resp.status_code == 404
