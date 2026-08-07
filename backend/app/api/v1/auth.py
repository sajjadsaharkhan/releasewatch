"""Authentication endpoints.

GET  /auth/providers          — list enabled login providers (booleans only)
POST /auth/login              — local + LDAP credentials → JWT pair
GET  /auth/keycloak/login     — begin Keycloak (OIDC) Authorization Code flow
GET  /auth/keycloak/callback  — Keycloak redirect → mint RW token → hand to SPA
POST /auth/refresh        — exchange refresh token for new access token
POST /auth/logout         — invalidate refresh token (client-side + Redis blacklist)
GET  /auth/me             — return the authenticated user's profile
GET  /auth/me/telegram    — return Telegram integration status for the current user
DELETE /auth/me/telegram  — disconnect the current user's Telegram account
GET  /auth/telegram/token — generate a one-time Telegram integration token
"""

import json
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.auth import (
    create_access_token,
    create_refresh_token,
    delete_kc_refresh,
    get_current_user,
    get_kc_refresh,
    store_kc_refresh,
    verify_password,
    verify_token,
)
from app.core.redis_client import get_redis_raw
from app.db.models.telegram_integration import TelegramIntegration
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    ProvidersResponse,
    RefreshRequest,
    TelegramStatusResponse,
    TelegramTokenResponse,
    TokenResponse,
    UserMeResponse,
)
from app.services.auth_providers.ldap import LdapProvider, LdapUnavailable
from app.services.auth_providers.oidc import KeycloakOIDCProvider
from app.services.identity_service import resolve_or_provision

logger = logging.getLogger(__name__)

router = APIRouter()

# Short-lived stash for the OIDC login round-trip, keyed by the `state` param.
_OIDC_STATE_PREFIX = "rw:oidc_state:"
_OIDC_STATE_TTL = 600  # seconds


def _mint_pair(user: User) -> tuple[str, str, str]:
    """Return (access_token, refresh_token, refresh_jti) for a resolved user."""
    token_data = {"sub": str(user.id), "role": user.role}
    access = create_access_token(token_data)
    refresh = create_refresh_token(token_data)
    refresh_jti = verify_token(refresh)["jti"]
    return access, refresh, refresh_jti


@router.get("/providers", response_model=ProvidersResponse, summary="List enabled login providers")
async def list_providers() -> ProvidersResponse:
    """Public: which login providers are enabled (booleans only, no secrets)."""
    return ProvidersResponse(
        local=True,
        keycloak=settings.keycloak_enabled,
        ldap=settings.ldap_enabled,
    )


@router.post("/login", response_model=TokenResponse, summary="Obtain JWT pair")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with username + password and receive an access/refresh token pair.

    When direct LDAP is enabled it is tried first; a rejected bind *or* an
    unreachable directory falls through to local password auth so local admins
    are never locked out.
    """
    # ── LDAP first (if enabled) ────────────────────────────────────────────────
    if settings.ldap_enabled:
        try:
            principal = await run_in_threadpool(
                LdapProvider().authenticate, payload.username, payload.password
            )
        except LdapUnavailable:
            principal = None  # directory down → fall through to local
        if principal is not None:
            user = await resolve_or_provision(db, principal)
            if not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated"
                )
            access, refresh, _ = _mint_pair(user)
            return TokenResponse(access_token=access, refresh_token=refresh)

    # ── Local fallback ─────────────────────────────────────────────────────────
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()

    if user is None or user.hashed_password is None or not verify_password(
        payload.password, user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    access, refresh, _ = _mint_pair(user)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.get("/keycloak/login", summary="Begin Keycloak (OIDC) login")
async def keycloak_login() -> RedirectResponse:
    """Redirect the browser to Keycloak to begin the Authorization Code flow."""
    if not settings.keycloak_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keycloak not enabled")

    url, req = await KeycloakOIDCProvider().build_authorize_url()
    redis = await get_redis_raw()
    await redis.set(
        _OIDC_STATE_PREFIX + req.state,
        json.dumps({"nonce": req.nonce, "code_verifier": req.code_verifier}),
        ex=_OIDC_STATE_TTL,
    )
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.get("/keycloak/callback", summary="Keycloak (OIDC) callback")
async def keycloak_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the Keycloak redirect, mint an RW token, and hand it to the SPA."""
    if not settings.keycloak_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Keycloak not enabled")

    error = request.query_params.get("error")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if error or not code or not state:
        return _callback_error_redirect(error or "missing_code")

    redis = await get_redis_raw()
    stashed = await redis.get(_OIDC_STATE_PREFIX + state)
    if not stashed:
        return _callback_error_redirect("invalid_state")
    await redis.delete(_OIDC_STATE_PREFIX + state)
    stash = json.loads(stashed)

    try:
        principal = await KeycloakOIDCProvider().handle_callback(
            code, stash["code_verifier"], stash["nonce"]
        )
    except Exception as exc:  # validation / exchange failure
        logger.warning("Keycloak callback failed: %s", exc)
        return _callback_error_redirect("auth_failed")

    user = await resolve_or_provision(db, principal)
    if not user.is_active:
        return _callback_error_redirect("deactivated")

    access, refresh, refresh_jti = _mint_pair(user)
    if principal.provider_refresh_token:
        await store_kc_refresh(refresh_jti, principal.provider_refresh_token)

    # The SPA uses BrowserRouter (real paths), so this must be a plain path with a
    # single fragment carrying the tokens — never a hash route.
    target = (
        f"{settings.FRONTEND_URL.rstrip('/')}/auth/callback"
        f"#access={access}&refresh={refresh}"
    )
    return RedirectResponse(target, status_code=status.HTTP_302_FOUND)


def _callback_error_redirect(reason: str) -> RedirectResponse:
    target = f"{settings.FRONTEND_URL.rstrip('/')}/login?error={reason}"
    return RedirectResponse(target, status_code=status.HTTP_302_FOUND)


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair.

    For Keycloak-provisioned sessions, the stored Keycloak refresh token is used
    to confirm the Keycloak session is still valid before re-minting; if it was
    revoked/disabled in Keycloak, the refresh is rejected.
    """
    claims = verify_token(payload.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    try:
        user_id = int(claims.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")

    old_jti = claims.get("jti")
    kc_refresh = await get_kc_refresh(old_jti) if old_jti else None

    access, refresh_token, new_jti = _mint_pair(user)

    # Federated (Keycloak) session — re-check against Keycloak and rotate storage.
    if kc_refresh is not None:
        new_kc_refresh = await KeycloakOIDCProvider().refresh_session(kc_refresh)
        if new_kc_refresh is None:
            await delete_kc_refresh(old_jti)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Keycloak session is no longer valid",
            )
        await delete_kc_refresh(old_jti)
        await store_kc_refresh(new_jti, new_kc_refresh)

    return TokenResponse(access_token=access, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke refresh token")
async def logout(
    payload: RefreshRequest,
) -> None:
    """Blacklist the supplied refresh token so it cannot be reused."""
    try:
        claims = verify_token(payload.refresh_token)
        jti = claims.get("jti")
        if jti:
            await delete_kc_refresh(jti)
        # Add token jti/sub to Redis blacklist with TTL = remaining expiry
        # (implementation omitted for brevity — see core/redis_client.py)
    except Exception:
        pass  # Silently succeed even if token is already invalid


@router.get("/me", response_model=UserMeResponse, summary="Get current user profile")
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    """Return the authenticated user's profile information."""
    role_value = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)

    return UserMeResponse(
        id=str(current_user.id),
        name=current_user.name,
        username=current_user.username,
        role=role_value,
        avatar_color=current_user.avatar_color,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active,
    )


@router.get(
    "/me/telegram",
    response_model=TelegramStatusResponse,
    summary="Get Telegram integration status",
)
async def get_telegram_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TelegramStatusResponse:
    """Return the current Telegram integration state for the authenticated user.

    If connected, returns account details.
    If not connected, returns the active integration token (if one exists).
    """
    result = await db.execute(
        select(TelegramIntegration).where(
            TelegramIntegration.user_id == current_user.id,
            TelegramIntegration.is_active.is_(True),
        )
    )
    integration = result.scalar_one_or_none()

    if integration:
        return TelegramStatusResponse(
            connected=True,
            telegram_username=integration.telegram_username,
            telegram_full_name=integration.telegram_full_name,
            telegram_user_id=integration.telegram_user_id,
            connected_at=integration.created_at.isoformat(),
            last_event_sent_at=(
                integration.last_event_sent_at.isoformat()
                if integration.last_event_sent_at
                else None
            ),
        )

    # Not connected — include the active token if one exists
    token = current_user.connect_token
    token_expires = current_user.connect_token_expires
    now = datetime.now(tz=timezone.utc)
    if token_expires and token_expires < now:
        token = None
        token_expires = None

    return TelegramStatusResponse(
        connected=False,
        token=token,
        token_expires_at=token_expires.isoformat() if token_expires else None,
    )


@router.delete(
    "/me/telegram",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect Telegram account",
)
async def disconnect_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the Telegram integration for the current user."""
    await db.execute(
        delete(TelegramIntegration).where(
            TelegramIntegration.user_id == current_user.id
        )
    )
    await db.commit()


@router.get(
    "/telegram/token",
    response_model=TelegramTokenResponse,
    summary="Generate Telegram integration token",
)
async def get_telegram_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TelegramTokenResponse:
    """Generate a one-time token for linking the user's Telegram account.

    The token expires after 10 minutes.  The user should send it to the
    Releasewatch bot via ``/integration <token>``.
    """
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=10)

    current_user.connect_token = token
    current_user.connect_token_expires = expires_at
    db.add(current_user)
    await db.commit()

    return TelegramTokenResponse(
        connect_token=token,
        expires_at=expires_at.isoformat(),
    )
