"""Characterization: POST /auth/login.

``client_for()`` mints tokens directly and deliberately never calls this
endpoint (docs/phase-2/01-test-harness.md's Auth helper decision) — this is
the one test that exercises the real login flow instead.
"""

import pytest


@pytest.mark.asyncio
async def test_login_succeeds_with_correct_credentials(client, factories):
    await factories.user(role="qa", username="login-qa")

    resp = await client.post(
        "/auth/login", json={"username": "login-qa", "password": "test-password-123"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]

    me = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == "login-qa"


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(client, factories):
    await factories.user(role="qa", username="login-qa-2")

    resp = await client.post(
        "/auth/login", json={"username": "login-qa-2", "password": "wrong-password-123"}
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_rejects_unknown_username(client):
    resp = await client.post(
        "/auth/login", json={"username": "nobody-here", "password": "whatever-12345"}
    )
    assert resp.status_code == 401
