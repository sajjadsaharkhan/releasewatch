"""Team management API — list members, invite, change role, deactivate."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_role
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.team import TeamMemberResponse, InviteRequest, ChangeRoleRequest

router = APIRouter()


@router.get("", response_model=list[TeamMemberResponse])
async def list_team(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active team members with Telegram connection status."""
    result = await db.execute(select(User).where(User.is_active == True).order_by(User.name))
    return result.scalars().all()


@router.post("/invite", response_model=TeamMemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    body: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.triage_lead)),
):
    """Invite a new team member — generates a Telegram connect token."""
    import secrets
    from datetime import datetime, timedelta, timezone

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    connect_token = secrets.token_urlsafe(32)
    user = User(
        id=uuid.uuid4(),
        name=body.name,
        username=body.username,
        email=body.email,
        role=UserRole(body.role),
        connect_token=connect_token,
        connect_token_expires=datetime.now(tz=timezone.utc) + timedelta(minutes=15),
        avatar_color=body.avatar_color or "#6366f1",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.patch("/{user_id}/role")
async def change_role(
    user_id: uuid.UUID,
    body: ChangeRoleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Change a team member's role (admin only)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.role = UserRole(body.role)
    await db.commit()
    return {"id": str(user.id), "role": user.role.value}


@router.patch("/{user_id}/deactivate")
async def deactivate_member(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Soft-deactivate a team member — they keep history but cannot log in."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    user.is_active = False
    await db.commit()
    return {"id": str(user.id), "is_active": False}
