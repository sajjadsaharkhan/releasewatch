"""Keycloak OIDC provider — backend-centric Authorization Code flow with PKCE.

Releasewatch drives the whole exchange server-side: it builds the authorize URL,
handles the callback, validates the ID token against the realm's JWKS, and then
mints its own token.  The frontend only ever redirects and receives the RW token.
"""

import base64
import hashlib
import logging
import secrets
from dataclasses import dataclass

import httpx

from app.config import settings
from app.services.auth_providers.base import ExternalPrincipal

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AuthRequestState:
    """Per-login transient state, stashed server-side keyed by ``state``."""

    state: str
    nonce: str
    code_verifier: str


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class KeycloakOIDCProvider:
    """Keycloak OIDC client (discovery + PKCE + JWKS validation)."""

    name = "keycloak"

    def __init__(self) -> None:
        self._metadata: dict | None = None
        self._jwks: dict | None = None

    # ── Discovery ─────────────────────────────────────────────────────────────
    async def _discover(self) -> dict:
        if self._metadata is None:
            url = settings.KEYCLOAK_ISSUER.rstrip("/") + "/.well-known/openid-configuration"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                self._metadata = resp.json()
        return self._metadata

    async def _get_jwks(self) -> dict:
        if self._jwks is None:
            meta = await self._discover()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(meta["jwks_uri"])
                resp.raise_for_status()
                self._jwks = resp.json()
        return self._jwks

    # ── Step 1: build the authorize redirect ──────────────────────────────────
    async def build_authorize_url(self) -> tuple[str, AuthRequestState]:
        """Return (authorize_url, transient_state) for the login redirect."""
        meta = await self._discover()
        code_verifier = _b64url(secrets.token_bytes(48))
        code_challenge = _b64url(hashlib.sha256(code_verifier.encode("ascii")).digest())
        req = AuthRequestState(
            state=secrets.token_urlsafe(24),
            nonce=secrets.token_urlsafe(24),
            code_verifier=code_verifier,
        )
        params = {
            "client_id": settings.KEYCLOAK_CLIENT_ID,
            "response_type": "code",
            "scope": settings.KEYCLOAK_SCOPES,
            "redirect_uri": settings.KEYCLOAK_REDIRECT_URI,
            "state": req.state,
            "nonce": req.nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        url = str(httpx.URL(meta["authorization_endpoint"], params=params))
        return url, req

    # ── Step 2: handle the callback ───────────────────────────────────────────
    async def handle_callback(self, code: str, code_verifier: str, expected_nonce: str) -> ExternalPrincipal:
        """Exchange the code, validate the ID token, and return a principal."""
        meta = await self._discover()
        async with httpx.AsyncClient(timeout=10) as client:
            token_resp = await client.post(
                meta["token_endpoint"],
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.KEYCLOAK_REDIRECT_URI,
                    "client_id": settings.KEYCLOAK_CLIENT_ID,
                    "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                    "code_verifier": code_verifier,
                },
            )
            token_resp.raise_for_status()
            tokens = token_resp.json()

        claims = await self._validate_id_token(tokens["id_token"], expected_nonce)
        return ExternalPrincipal(
            provider=self.name,
            subject=claims["sub"],
            username=claims.get("preferred_username") or claims.get("sub"),
            name=claims.get("name"),
            email=claims.get("email"),
            provider_refresh_token=tokens.get("refresh_token"),
        )

    async def _validate_id_token(self, id_token: str, expected_nonce: str) -> dict:
        from authlib.jose import JsonWebKey, jwt
        from authlib.jose.errors import JoseError

        meta = await self._discover()
        jwks = await self._get_jwks()
        keyset = JsonWebKey.import_key_set(jwks)
        claims_options = {
            "iss": {"essential": True, "value": meta["issuer"]},
            "aud": {"essential": True, "value": settings.KEYCLOAK_CLIENT_ID},
        }
        try:
            claims = jwt.decode(id_token, keyset, claims_options=claims_options)
            claims.validate()  # exp / iat / iss / aud
        except JoseError as exc:
            logger.warning("Keycloak ID token validation failed: %s", exc)
            raise ValueError("Invalid ID token") from exc

        if claims.get("nonce") != expected_nonce:
            raise ValueError("Nonce mismatch")
        return dict(claims)

    async def refresh_session(self, kc_refresh_token: str) -> str | None:
        """Refresh the Keycloak session; return the NEW KC refresh token or ``None``.

        ``None`` means the session is no longer valid (user revoked/disabled) and
        the RW refresh must be rejected.
        """
        meta = await self._discover()
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    meta["token_endpoint"],
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": kc_refresh_token,
                        "client_id": settings.KEYCLOAK_CLIENT_ID,
                        "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                    },
                )
            if resp.status_code != 200:
                return None
            return resp.json().get("refresh_token", kc_refresh_token)
        except httpx.HTTPError as exc:
            logger.warning("Keycloak refresh failed: %s", exc)
            return None
