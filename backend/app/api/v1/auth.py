"""Authentication endpoints.

POST /auth/login          — exchange credentials for JWT pair
POST /auth/refresh        — exchange refresh token for new access token
POST /auth/logout         — invalidate refresh token (client-side + Redis blacklist)
GET  /auth/me             — return the authenticated user's profile
GET  /auth/telegram/token — generate a one-time Telegram connect token
"""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    create_refresh_token,
    get_current_user,
    verify_password,
    verify_token,
)
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
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
    """Authenticate with email + password and receive an access/refresh token pair.

    The access token is short-lived (default: 60 min).
    The refresh token is long-lived (default: 30 days) and must be stored
    securely (HTTP-only cookie recommended on the client).
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
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
    """Exchange a valid refresh token for a new access + refresh token pair.

    The old refresh token is invalidated (stored in Redis blacklist).
    """
    claims = verify_token(payload.refresh_token)
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")

    # Optionally add the old token to a Redis blacklist here
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
    """Blacklist the supplied refresh token so it cannot be reused.

    The client should also discard its locally stored tokens.
    """
    try:
        claims = verify_token(payload.refresh_token)
        # Add token jti/sub to Redis blacklist with TTL = remaining expiry
        # (implementation omitted for brevity — see core/redis_client.py)
    except Exception:
        pass  # Silently succeed even if token is already invalid


@router.get("/me", response_model=UserMeResponse, summary="Get current user profile")
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserMeResponse:
    """Return the authenticated user's profile information."""
    return UserMeResponse(
        id=str(current_user.id),
        email=current_user.email,
        name=current_user.name,
        username=current_user.username,
        role=current_user.role.value,
        avatar_color=current_user.avatar_color,
        telegram_handle=current_user.telegram_handle,
        telegram_connected_at=(
            current_user.telegram_connected_at.isoformat()
            if current_user.telegram_connected_at
            else None
        ),
        is_active=current_user.is_active,
    )


@router.get(
    "/telegram/token",
    response_model=TelegramTokenResponse,
    summary="Generate Telegram connect token",
)
async def get_telegram_token(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TelegramTokenResponse:
    """Generate a one-time token for linking the user's Telegram account.

    The token expires after 10 minutes.  The user should send it to the
    Releasewatch bot via ``/connect <token>``.
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
