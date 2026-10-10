"""Keycloak-backed sessions: login via the OIDC callback, then POST /auth/refresh.

Keycloak itself is faked at the provider boundary (``handle_callback`` and
``refresh_session``); everything from the callback route onward is real.
"""

import json
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from jose import jwt

from app.config import settings
from app.core.auth import delete_kc_refresh, get_kc_refresh
from app.core.redis_client import get_redis_raw
from app.services.auth_providers.base import ExternalPrincipal
from app.services.auth_providers.oidc import (
    KeycloakOIDCProvider,
    KeycloakRefresh,
    KeycloakUnavailable,
)

KC_IDLE_SECONDS = 1800  # Keycloak's default SSO Session Idle


class FakeKeycloak:
    """Stands in for the realm: issues refresh tokens and can reject or fail."""

    def __init__(self) -> None:
        self.mode = "ok"  # "ok" | "reject" | "down"
        self.refreshed_with: list[str] = []
        self._n = 0

    def _next_token(self) -> str:
        self._n += 1
        return f"kc-refresh-{self._n}"

    async def handle_callback(self, code, code_verifier, nonce) -> ExternalPrincipal:
        return ExternalPrincipal(
            provider="keycloak",
            subject="kc-sub-1",
            username="kc-user",
            name="KC User",
            email="kc-user@example.com",
            provider_refresh_token=self._next_token(),
            provider_refresh_expires_in=KC_IDLE_SECONDS,
        )

    async def refresh_session(self, kc_refresh_token: str) -> KeycloakRefresh | None:
        self.refreshed_with.append(kc_refresh_token)
        if self.mode == "down":
            raise KeycloakUnavailable("connect timeout")
        if self.mode == "reject":
            return None
        return KeycloakRefresh(refresh_token=self._next_token(), refresh_expires_in=KC_IDLE_SECONDS)


@pytest.fixture
def keycloak(monkeypatch: pytest.MonkeyPatch) -> FakeKeycloak:
    monkeypatch.setattr(settings, "KEYCLOAK_ISSUER", "https://kc.test/realms/rw")
    monkeypatch.setattr(settings, "KEYCLOAK_CLIENT_ID", "rw")
    monkeypatch.setattr(settings, "KEYCLOAK_CLIENT_SECRET", "test-secret")
    monkeypatch.setattr(settings, "KEYCLOAK_REDIRECT_URI", "http://test/api/v1/auth/keycloak/callback")
    fake = FakeKeycloak()
    monkeypatch.setattr(KeycloakOIDCProvider, "handle_callback", fake.handle_callback)
    monkeypatch.setattr(KeycloakOIDCProvider, "refresh_session", fake.refresh_session)
    return fake


def _claims(token: str) -> dict:
    return jwt.get_unverified_claims(token)


def _lifetime_seconds(token: str) -> float:
    exp = datetime.fromtimestamp(_claims(token)["exp"], tz=timezone.utc)
    return (exp - datetime.now(tz=timezone.utc)).total_seconds()


async def _keycloak_login(client) -> tuple[str, str]:
    """Drive the callback route and return the (access, refresh) pair it hands the SPA."""
    state = "state-123"
    await (await get_redis_raw()).set(
        "rw:oidc_state:" + state, json.dumps({"nonce": "n", "code_verifier": "v"}), ex=600
    )
    resp = await client.get("/auth/keycloak/callback", params={"code": "c", "state": state})
    assert resp.status_code == 302
    location = urlparse(resp.headers["location"])
    assert location.path == "/auth/callback"
    fragment = parse_qs(location.fragment)
    return fragment["access"][0], fragment["refresh"][0]


@pytest.mark.asyncio
async def test_keycloak_access_token_expires_well_inside_the_idle_window(client, keycloak):
    access, refresh = await _keycloak_login(client)

    # Half of the 30-minute idle window, so an active user refreshes (and resets
    # Keycloak's idle timer) long before Keycloak would expire the session.
    assert 14 * 60 < _lifetime_seconds(access) <= 15 * 60
    assert _claims(refresh)["idp"] == "keycloak"


@pytest.mark.asyncio
async def test_refresh_renews_the_keycloak_session(client, keycloak):
    _, refresh = await _keycloak_login(client)

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})

    assert resp.status_code == 200
    body = resp.json()
    assert keycloak.refreshed_with == ["kc-refresh-1"]
    assert await get_kc_refresh(_claims(body["refresh_token"])["jti"]) == "kc-refresh-2"
    assert _lifetime_seconds(body["access_token"]) <= 15 * 60
    me = await client.get("/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.json()["username"] == "kc-user"


@pytest.mark.asyncio
async def test_refresh_is_rejected_when_keycloak_ends_the_session(client, keycloak):
    _, refresh = await _keycloak_login(client)
    keycloak.mode = "reject"

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_keycloak_outage_is_a_503_and_keeps_the_session(client, keycloak):
    _, refresh = await _keycloak_login(client)
    keycloak.mode = "down"

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 503

    keycloak.mode = "ok"
    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_two_tabs_refreshing_with_the_same_token_both_stay_signed_in(client, keycloak):
    _, refresh = await _keycloak_login(client)

    first = await client.post("/auth/refresh", json={"refresh_token": refresh})
    second = await client.post("/auth/refresh", json={"refresh_token": refresh})

    assert first.status_code == 200
    assert second.status_code == 200
    # The second tab rides on the session the first tab just renewed, and is
    # still a Keycloak-backed session — it never degrades to a local one.
    assert keycloak.refreshed_with == ["kc-refresh-1", "kc-refresh-2"]
    assert _claims(second.json()["refresh_token"])["idp"] == "keycloak"


@pytest.mark.asyncio
async def test_keycloak_session_never_degrades_to_a_local_one(client, keycloak):
    _, refresh = await _keycloak_login(client)
    await delete_kc_refresh(_claims(refresh)["jti"])

    resp = await client.post("/auth/refresh", json={"refresh_token": refresh})

    assert resp.status_code == 401
    assert keycloak.refreshed_with == []


@pytest.mark.asyncio
async def test_local_session_refresh_never_calls_keycloak(client, factories, keycloak):
    await factories.user(role="qa", username="local-refresh")
    login = await client.post(
        "/auth/login", json={"username": "local-refresh", "password": "test-password-123"}
    )

    resp = await client.post("/auth/refresh", json={"refresh_token": login.json()["refresh_token"]})

    assert resp.status_code == 200
    assert "idp" not in _claims(resp.json()["refresh_token"])
    assert keycloak.refreshed_with == []
