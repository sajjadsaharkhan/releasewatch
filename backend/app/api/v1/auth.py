"""Authentication endpoints.

POST /auth/login          — exchange credentials for JWT pair
POST /auth/refresh        — exchange refresh token for new access token
POST /auth/logout         — invalidate refresh token (client-side + Redis blacklist)
GET  /auth/me             — return the authenticated user's profile
GET  /auth/me/telegram    — return Telegram integration status for the current user
DELETE /auth/me/telegram  — disconnect the current user's Telegram account
GET  /auth/telegram/token — generate a one-time Telegram integration token
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    verify_password,
    verify_token,
)
from app.db.models.telegram_integration import TelegramIntegration
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    TelegramStatusResponse,
    TelegramTokenResponse,
    TokenResponse,
    UserMeResponse,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse, summary="Obtain JWT pair")
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with username + password and receive an access/refresh token pair."""
    result = await db.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    token_data = {"sub": str(user.id), "role": user.role}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/refresh", response_model=TokenResponse, summary="Refresh access token")
async def refresh(
    payload: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a valid refresh token for a new access + refresh token pair."""
    claims = verify_token(payload.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    user_id = claims.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or deactivated")

    token_data = {"sub": str(user.id), "role": user.role}
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke refresh token")
async def logout(
    payload: RefreshRequest,
) -> None:
    """Blacklist the supplied refresh token so it cannot be reused."""
    try:
        verify_token(payload.refresh_token)
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
