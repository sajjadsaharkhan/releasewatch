"""Slice 15 — MCP connection and tokens.

docs/phase-2/15-mcp-connection-and-tokens.md (prd-mcp.md FR-M01, FR-M38–M45,
BR-M02–M04, BR-M20–M24, AC-M02, AC-M04, AC-M36–M40, §8). Token management is
driven at the ``/api/v1`` seam; ``/mcp`` through the in-process MCP client
(``mcp_client_for``). The expiry notice is the scheduled-job body called with ``now``.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app as fastapi_app

DISABLED = "MCP is disabled by the administrator"


def _result(res) -> dict:
    """A tool result's JSON body (structured content, else the text block)."""
    if res.structured_content is not None:
        return res.structured_content
    return json.loads(res.content[0].text)


def _at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


async def _enable(admin, enabled: bool = True) -> None:
    assert (await admin.put("/settings/mcp", json={"enabled": enabled})).status_code == 200


async def _my_tokens(client) -> list[dict]:
    resp = await client.get("/me/mcp")
    assert resp.status_code == 200, resp.text
    return resp.json()["tokens"]


async def _run_expiry_notices(now: datetime):
    from app.tasks.mcp import notify_expiring_mcp_tokens

    return await notify_expiring_mcp_tokens(now)


# ── The profile section and the token value (FR-M38–M42) ────────────────────


@pytest.mark.asyncio
async def test_mcp_is_disabled_on_a_new_installation(factories, client_for):
    dev = await factories.user(role="developer")
    body = (await (await client_for(dev)).get("/me/mcp")).json()
    assert body["enabled"] is False
    admin_view = (await factories.admin_client.get("/settings/mcp")).json()
    assert admin_view == {"enabled": False, "tokens": []}


@pytest.mark.asyncio
async def test_ac_m36_create_shows_value_and_configs_once_and_notifies(
    factories, client_for, telegram,
):
    dev = await factories.user(role="developer")
    await telegram.link_telegram(dev)
    await _enable(factories.admin_client)
    c = await client_for(dev)

    resp = await c.post("/me/mcp/tokens", json={"name": "Claude Code — laptop"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    value = body["value"]
    assert value.startswith("rwm_") and len(value) > 40
    me = (await c.get("/me/mcp")).json()
    assert me["base_url"].endswith("/mcp")
    assert set(body["configs"]) == {"claude_code", "codex", "zcode"}
    for config in body["configs"].values():
        assert value in config and me["base_url"] in config

    # FR-M41: the clients and what each supports are product content from the server.
    assert {cl["key"] for cl in me["clients"]} == {"claude_code", "codex", "zcode"}
    for cl in me["clients"]:
        assert {"name", "supports_prompts", "supports_resources"} <= set(cl)

    # BR-M21: no later response carries the value or its hash.
    for listing in (me, (await factories.admin_client.get("/settings/mcp")).json()):
        text = json.dumps(listing)
        assert value not in text and "token_hash" not in text and '"value"' not in text
    [token] = me["tokens"]
    assert token["name"] == "Claude Code — laptop"
    assert token["status"] == "active"
    assert value.startswith(token["token_prefix"])
    assert token["last_used_at"] is None

    # §8: Telegram to the owner, with name and expiry.
    sent = telegram.sent_to(dev)
    assert [t for t, _ in sent] == ["mcp_token_created"]
    ctx = sent[0][1]
    assert ctx["token_name"] == "Claude Code — laptop" and ctx["expires_on"]
    inbox = (await c.get("/inbox", params={"event_type": "mcp_token_created"})).json()
    assert inbox["total"] == 1


@pytest.mark.asyncio
async def test_ac_m37_lifetimes_are_30_90_or_365_days_with_90_preselected(
    factories, client_for, clock,
):
    dev = await factories.user(role="developer")
    await _enable(factories.admin_client)
    c = await client_for(dev)
    now = datetime(2030, 3, 1, 12, tzinfo=UTC)
    clock.set(now)

    default = (await c.post("/me/mcp/tokens", json={"name": "default"})).json()["token"]
    assert _at(default["expires_at"]) == now + timedelta(days=90)
    for days in (30, 90, 365):
        resp = await c.post("/me/mcp/tokens", json={"name": f"d{days}", "lifetime_days": days})
        assert resp.status_code == 201
        assert _at(resp.json()["token"]["expires_at"]) == now + timedelta(days=days)

    # BR-M20: no other lifetime, and none without expiry.
    for bad in (7, 0, None, 3650):
        resp = await c.post("/me/mcp/tokens", json={"name": "x", "lifetime_days": bad})
        assert resp.status_code == 422, bad
    assert (await c.post("/me/mcp/tokens", json={"name": "  "})).status_code == 422
    assert (await c.post("/me/mcp/tokens", json={"name": "x" * 65})).status_code == 422


@pytest.mark.asyncio
async def test_ac_m04_support_has_no_mcp_section_and_cannot_create(factories, client_for):
    support = await factories.user(role="support")
    await _enable(factories.admin_client)
    c = await client_for(support)
    assert (await c.get("/me/mcp")).status_code == 403
    assert (await c.post("/me/mcp/tokens", json={"name": "x"})).status_code == 403


@pytest.mark.asyncio
async def test_every_tech_role_can_hold_tokens(factories, mcp_token):
    for role in ("qa", "developer", "product_manager", "cto", "admin"):
        user = await factories.user(role=role)
        assert (await mcp_token(user)).status == "active"


@pytest.mark.asyncio
async def test_revoke_own_token_and_another_users_token_is_404(
    factories, client_for, mcp_token, mcp_client_for,
):
    dev = await factories.user(role="developer")
    other = await factories.user(role="qa")
    token = await mcp_token(dev)
    theirs = await mcp_token(other)
    c = await client_for(dev)

    assert (await c.post(f"/me/mcp/tokens/{theirs.id}/revoke")).status_code == 404
    assert (await c.post("/me/mcp/tokens/999999/revoke")).status_code == 404
    resp = await c.post(f"/me/mcp/tokens/{token.id}/revoke")
    assert resp.status_code == 200
    assert resp.json()["status"] == "revoked"
    # Revoked tokens leave the list (D19); the row is kept (BR-M24), so a second
    # revoke still finds it.
    assert await _my_tokens(c) == []
    again = await c.post(f"/me/mcp/tokens/{token.id}/revoke")
    assert again.status_code == 200 and again.json()["revoked_at"] == resp.json()["revoked_at"]
    # The other user's token is untouched.
    assert _result(await (await mcp_client_for(other, theirs)).call("rw_context"))


# ── /mcp and rw_context (FR-M01, BR-M03) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_rw_context_returns_user_visible_projects_and_jev(factories, mcp_client_for):
    admin = factories.admin_client
    dev = await factories.user(role="developer", name="Dana Dev")
    a = await factories.project(name="Alpha")
    b = await factories.project(name="Beta")
    gone = await factories.project(name="Gone")
    assert (await admin.delete(f"/projects/{gone.slug}")).status_code in (200, 204)

    body = _result(await (await mcp_client_for(dev)).call("rw_context"))
    assert body["user"] == {"name": "Dana Dev", "username": dev.username, "role": "developer"}
    assert body["jev_enabled"] is False
    # Tech roles see every project (BR-30); archived ones are left out.
    assert sorted(p["key"] for p in body["projects"]) == sorted([a.slug, b.slug])
    assert {p["name"] for p in body["projects"]} == {"Alpha", "Beta"}

    admin_user = await factories.user(role="admin")
    admin_body = _result(await (await mcp_client_for(admin_user)).call("rw_context"))
    assert sorted(p["key"] for p in admin_body["projects"]) == sorted([a.slug, b.slug])


@pytest.mark.asyncio
async def test_last_used_at_is_written_at_most_once_a_minute(
    factories, client_for, mcp_client_for,
):
    from app.core.redis_client import get_redis_raw

    dev = await factories.user(role="developer")
    session = await mcp_client_for(dev)
    c = await client_for(dev)

    await session.call("rw_context")
    [first] = await _my_tokens(c)
    assert first["last_used_at"] is not None
    await session.call("rw_context")
    [second] = await _my_tokens(c)
    assert second["last_used_at"] == first["last_used_at"]

    # Once the minute's Redis key is gone, the next request writes it again.
    redis = await get_redis_raw()
    for key in await redis.keys("rw:mcp:touch:*"):
        await redis.delete(key)
    await session.call("rw_context")
    [third] = await _my_tokens(c)
    assert _at(third["last_used_at"]) > _at(first["last_used_at"])


@pytest.mark.asyncio
async def test_unknown_token_and_missing_header_are_refused(factories):
    from tests.conftest import McpSession

    await _enable(factories.admin_client)
    refused = await McpSession("rwm_" + "x" * 43).refusal()
    assert refused.code == "token_invalid"
    async with AsyncClient(transport=ASGITransport(app=fastapi_app), base_url="http://test") as raw:
        resp = await raw.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
    assert resp.status_code == 401
    assert resp.json()["error"]["data"]["code"] == "token_invalid"


@pytest.mark.asyncio
async def test_owner_who_is_no_longer_tech_is_refused_not_tech(
    factories, mcp_token, mcp_client_for,
):
    dev = await factories.user(role="developer")
    token = await mcp_token(dev)
    resp = await factories.admin_client.patch(f"/team/{dev.id}/role", json={"role": "support"})
    assert resp.status_code == 200
    assert (await (await mcp_client_for(dev, token)).refusal()).code == "not_tech"


# ── AC-M02 / BR-M02: each credential works on its own side only ──────────────


@pytest.mark.asyncio
async def test_ac_m02_mcp_token_is_refused_by_the_web_api(factories, mcp_token):
    dev = await factories.user(role="developer")
    token = await mcp_token(dev)
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test/api/v1",
        headers={"Authorization": f"Bearer {token.value}"},
    ) as c:
        for path in ("/inbox", "/me/mcp", "/projects"):
            assert (await c.get(path)).status_code == 401, path


@pytest.mark.asyncio
async def test_ac_m02_web_session_is_refused_by_the_mcp_server(factories):
    from app.core.auth import create_access_token
    from tests.conftest import McpSession

    dev = await factories.user(role="developer")
    await _enable(factories.admin_client)
    jwt = create_access_token({"sub": str(dev.id), "role": "developer"})
    assert (await McpSession(jwt).refusal()).code == "token_invalid"


# ── AC-M39 / BR-M22: expired, revoked, deactivated owner ─────────────────────


@pytest.mark.asyncio
async def test_ac_m39_expired_token_is_refused_and_cannot_be_renewed(
    factories, client_for, mcp_client_for, clock,
):
    dev = await factories.user(role="developer")
    await _enable(factories.admin_client)
    c = await client_for(dev)
    body = (await c.post("/me/mcp/tokens", json={"name": "old", "lifetime_days": 30})).json()
    session = await mcp_client_for(dev, body["value"])
    clock.advance(days=29)
    assert _result(await session.call("rw_context"))
    clock.advance(days=1)

    assert (await session.refusal()).code == "token_invalid"
    [listed] = await _my_tokens(c)
    assert listed["status"] == "expired"
    # FR-M42: there is no renewal endpoint.
    assert (await c.post(f"/me/mcp/tokens/{listed['id']}/renew")).status_code in (404, 405)


@pytest.mark.asyncio
async def test_ac_m39_revoked_token_is_refused_on_its_next_request(
    factories, client_for, mcp_token, mcp_client_for,
):
    dev = await factories.user(role="developer")
    token = await mcp_token(dev)
    session = await mcp_client_for(dev, token)
    assert _result(await session.call("rw_context"))["user"]["username"] == dev.username

    revoked = await (await client_for(dev)).post(f"/me/mcp/tokens/{token.id}/revoke")
    assert revoked.status_code == 200
    assert (await session.refusal()).code == "token_invalid"


@pytest.mark.asyncio
async def test_ac_m39_deactivated_owners_tokens_are_refused(
    factories, mcp_token, mcp_client_for,
):
    dev = await factories.user(role="developer")
    token = await mcp_token(dev)
    session = await mcp_client_for(dev, token)
    assert (await factories.admin_client.patch(f"/team/{dev.id}/deactivate")).status_code == 200
    assert (await session.refusal()).code == "token_invalid"
    # Not revoked one by one: reactivating brings it back.
    assert (await factories.admin_client.patch(f"/team/{dev.id}/activate")).status_code == 200
    assert _result(await session.call("rw_context"))


# ── AC-M40: the kill switch (FR-M43–M45) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_ac_m40_disabled_mcp_refuses_everything_and_keeps_tokens(
    factories, client_for, mcp_token, mcp_client_for,
):
    admin = factories.admin_client
    dev = await factories.user(role="developer")
    keep = await mcp_token(dev, name="keep")
    drop = await mcp_token(dev, name="drop")
    session = await mcp_client_for(dev, keep)
    c = await client_for(dev)

    await _enable(admin, False)
    refused = await session.refusal()
    assert refused.code == "mcp_disabled" and refused.message == DISABLED
    # Even a bad token learns only that MCP is off.
    from tests.conftest import McpSession

    assert (await McpSession("rwm_nope").refusal()).code == "mcp_disabled"

    # FR-M43: creation unavailable; tokens listed and revocable.
    resp = await c.post("/me/mcp/tokens", json={"name": "new"})
    assert resp.status_code == 409 and resp.json()["code"] == "mcp_disabled"
    assert resp.json()["detail"] == DISABLED
    me = (await c.get("/me/mcp")).json()
    assert me["enabled"] is False
    assert {t["name"]: t["status"] for t in me["tokens"]} == {"keep": "active", "drop": "active"}
    assert (await c.post(f"/me/mcp/tokens/{drop.id}/revoke")).status_code == 200
    assert [t["name"] for t in await _my_tokens(c)] == ["keep"]

    await _enable(admin, True)
    assert _result(await session.call("rw_context"))["user"]["username"] == dev.username
    assert (await (await mcp_client_for(dev, drop)).refusal()).code == "token_invalid"


# ── Settings → MCP (FR-M44) ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_lists_and_revokes_every_users_token(
    factories, client_for, mcp_token, mcp_client_for,
):
    admin = factories.admin_client
    dev = await factories.user(role="developer", name="Dana Dev")
    qa = await factories.user(role="qa")
    dev_token = await mcp_token(dev, name="laptop")
    await mcp_token(qa, name="desktop")

    body = (await admin.get("/settings/mcp")).json()
    assert body["enabled"] is True
    rows = {t["name"]: t for t in body["tokens"]}
    assert set(rows) == {"laptop", "desktop"}
    assert rows["laptop"]["user"]["username"] == dev.username
    assert rows["laptop"]["user"]["name"] == "Dana Dev"
    for key in ("created_at", "expires_at", "last_used_at", "status"):
        assert key in rows["laptop"]

    resp = await admin.post(f"/settings/mcp/tokens/{dev_token.id}/revoke")
    assert resp.status_code == 200 and resp.json()["status"] == "revoked"
    listed = {t["name"] for t in (await admin.get("/settings/mcp")).json()["tokens"]}
    assert listed == {"desktop"}
    assert (await (await mcp_client_for(dev, dev_token)).refusal()).code == "token_invalid"
    assert (await admin.post("/settings/mcp/tokens/999999/revoke")).status_code == 404


@pytest.mark.asyncio
async def test_settings_mcp_is_admin_and_cto_only(factories, client_for):
    cto = await factories.user(role="cto")
    cto_c = await client_for(cto)
    assert (await cto_c.get("/settings/mcp")).status_code == 200
    assert (await cto_c.put("/settings/mcp", json={"enabled": True})).status_code == 200
    for role in ("developer", "qa", "product_manager", "support"):
        c = await client_for(await factories.user(role=role))
        assert (await c.get("/settings/mcp")).status_code == 403, role
        assert (await c.put("/settings/mcp", json={"enabled": False})).status_code == 403, role
        assert (await c.post("/settings/mcp/tokens/1/revoke")).status_code == 403, role


# ── AC-M38: one notice seven days before expiry (§8) ─────────────────────────


@pytest.mark.asyncio
async def test_ac_m38_one_telegram_notice_seven_days_before_expiry(
    factories, client_for, mcp_token, telegram,
):
    dev = await factories.user(role="developer")
    await telegram.link_telegram(dev)
    token = await mcp_token(dev, name="laptop", lifetime_days=30)
    revoked = await mcp_token(dev, name="gone", lifetime_days=30)
    await (await client_for(dev)).post(f"/me/mcp/tokens/{revoked.id}/revoke")
    later = await mcp_token(dev, name="later", lifetime_days=90)
    expires = _at(token.expires_at)

    def expiring():
        return [ctx for t, ctx in telegram.sent_to(dev) if t == "mcp_token_expiring"]

    await _run_expiry_notices(expires - timedelta(days=8))
    assert expiring() == []

    await _run_expiry_notices(expires - timedelta(days=6, hours=23))
    await _run_expiry_notices(expires - timedelta(days=6))
    [ctx] = expiring()
    assert ctx["token_name"] == "laptop" and ctx["expires_on"]
    inbox = (await (await client_for(dev)).get(
        "/inbox", params={"event_type": "mcp_token_expiring"},
    )).json()
    assert inbox["total"] == 1

    # Tokens already expired get no notice; the revoked one never does.
    await _run_expiry_notices(_at(later.expires_at) + timedelta(days=1))
    assert [c["token_name"] for c in expiring()] == ["laptop"]


@pytest.mark.asyncio
async def test_no_expiry_notice_for_an_owner_who_can_no_longer_use_the_token(
    factories, mcp_token, telegram,
):
    admin = factories.admin_client
    moved = await factories.user(role="developer")
    gone = await factories.user(role="qa")
    for user in (moved, gone):
        await telegram.link_telegram(user)
    moved_token = await mcp_token(moved, lifetime_days=30)
    await mcp_token(gone, lifetime_days=30)
    assert (await admin.patch(f"/team/{moved.id}/role", json={"role": "support"})).status_code == 200
    assert (await admin.patch(f"/team/{gone.id}/deactivate")).status_code == 200

    notified = await _run_expiry_notices(_at(moved_token.expires_at) - timedelta(days=6))
    assert notified == []
    for user in (moved, gone):
        assert [t for t, _ in telegram.sent_to(user) if t == "mcp_token_expiring"] == []
