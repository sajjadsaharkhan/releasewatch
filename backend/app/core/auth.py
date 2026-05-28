"""Authentication utilities — JWT creation/verification and FastAPI dependencies.

Typical usage
-------------
    # In a route file
    from app.core.auth import get_current_user, require_role
    from app.db.models.user import UserRole

    @router.get("/admin-only")
    async def admin_route(current_user = Depends(require_role(UserRole.admin))):
        ...
"""

import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.user import User, UserRole
from app.db.session import get_db

# ── Password hashing ──────────────────────────────────────────────────────────


def get_password_hash(password: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return ``True`` if ``plain_password`` matches the stored bcrypt hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


# ── OAuth2 bearer scheme (reads token from Authorization: Bearer <token>) ─────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Token creation ────────────────────────────────────────────────────────────

def _build_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    """Internal helper — sign a JWT with an expiry embedded as ``exp`` claim."""
    payload = data.copy()
    payload["exp"] = datetime.now(tz=timezone.utc) + expires_delta
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(data: dict[str, Any]) -> str:
    """Create a short-lived access JWT.

    Parameters
    ----------
    data:
        Arbitrary claims to embed.  Must include ``"sub"`` (user ID as string).

    Returns
    -------
    str
        Signed JWT string.
    """
    return _build_token(
        {**data, "type": "access"},
        timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES),
    )


def create_refresh_token(data: dict[str, Any]) -> str:
    """Create a long-lived refresh JWT used to obtain a new access token.

    Parameters
    ----------
    data:
        Arbitrary claims.  Must include ``"sub"`` (user ID as string).
    """
    return _build_token(
        {**data, "type": "refresh"},
        timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    )


# ── Token verification ────────────────────────────────────────────────────────

def verify_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT.

    Raises
    ------
    HTTPException(401)
        If the token is expired, malformed, or has an invalid signature.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise credentials_exception
    return payload


# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI dependency — resolve the Bearer token to an active ``User`` row.

    Raises
    ------
    HTTPException(401)
        If the token is invalid or the user no longer exists.
    HTTPException(403)
        If the user account has been deactivated.
    """
    payload = verify_token(token)
    user_id_str: str | None = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_id = int(user_id_str)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID in token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")
    return user


def require_role(*roles: UserRole):
    """Dependency factory — restrict access to users with one of the given roles.

    Usage::

        @router.delete("/projects/{slug}")
        async def delete_project(
            _: User = Depends(require_role(UserRole.admin, UserRole.cto))
        ):
            ...
    """

    async def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {[r.value for r in roles]}",
            )
        return current_user

    return _check_role
