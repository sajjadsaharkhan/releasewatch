"""Team management API — list members, invite, change role, deactivate."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_role, get_password_hash, verify_password
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.team import TeamMemberResponse, MemberResponse, InviteRequest, ChangeRoleRequest, UserUpdateRequest
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("", response_model=list[MemberResponse])
async def list_team(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active team members with Telegram connection status."""
    result = await db.execute(
        select(User)
        .where(User.is_active == True)
        .order_by(User.is_active.desc(), User.name)
    )
    users = result.scalars().all()

    # Convert to MemberResponse with computed fields
    return [
        MemberResponse(
            id=user.id,
            name=user.name,
            username=user.username,
            role=user.role,
            avatar_url=user.avatar_url,
            avatar_color=user.avatar_color,
            telegram_handle=user.telegram_handle,
            is_active=user.is_active,
            created_at=user.created_at,
            title=user.title,
            bio=user.bio,
            tgConnected=user.telegram_handle is not None,
            reported=0,  # TODO: compute from issues
            fixed=0,     # TODO: compute from issues
            avgFixTime=None,
            fixRate=None,
        )
        for user in users
    ]


@router.get("/all", response_model=list[MemberResponse])
async def list_all_team(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all team members including inactive ones (for Settings page)."""
    result = await db.execute(
        select(User).order_by(User.is_active.desc(), User.name)
    )
    users = result.scalars().all()

    # Convert to MemberResponse with computed fields
    return [
        MemberResponse(
            id=user.id,
            name=user.name,
            username=user.username,
            role=user.role,
            avatar_url=user.avatar_url,
            avatar_color=user.avatar_color,
            telegram_handle=user.telegram_handle,
            is_active=user.is_active,
            created_at=user.created_at,
            title=user.title,
            bio=user.bio,
            tgConnected=user.telegram_handle is not None,
            reported=0,  # TODO: compute from issues
            fixed=0,     # TODO: compute from issues
            avgFixTime=None,
            fixRate=None,
        )
        for user in users
    ]


@router.post("/invite", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    body: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.triage_lead)),
):
    """Create a new team member with username and password."""
    import secrets
    from datetime import datetime, timedelta, timezone

    # Check if username already exists
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    connect_token = secrets.token_urlsafe(32)
    user = User(
        name=body.name,
        username=body.username,
        hashed_password=get_password_hash(body.temporary_password),
        role=UserRole(body.role),
        connect_token=connect_token,
        connect_token_expires=datetime.now(tz=timezone.utc) + timedelta(minutes=15),
        avatar_color=body.avatar_color or "#6366f1",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return MemberResponse(
        id=user.id,
        name=user.name,
        username=user.username,
        role=user.role,
        avatar_url=user.avatar_url,
        avatar_color=user.avatar_color,
        telegram_handle=user.telegram_handle,
        is_active=user.is_active,
        created_at=user.created_at,
        title=user.title,
        bio=user.bio,
        tgConnected=user.telegram_handle is not None,
        reported=0,
        fixed=0,
        avgFixTime=None,
        fixRate=None,
    )


@router.patch("/{user_id}/role")
async def change_role(
    user_id: int,
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


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a team member's profile (name, username, title, bio, avatar_color, password).
    Admins can edit anyone. Users can edit their own profile (except role).
    Password changes only allowed by admins or for self.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Only admins can change role and password of others
    is_admin = current_user.role == UserRole.admin
    is_self = current_user.id == user.id

    if not is_admin and not is_self:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only edit your own profile"
        )

    if body.name is not None:
        user.name = body.name
    if body.username is not None:
        # Check if username is already taken
        existing = await db.execute(select(User).where(User.username == body.username, User.id != user_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
        user.username = body.username
    if body.title is not None:
        user.title = body.title
    if body.bio is not None:
        user.bio = body.bio
    if body.avatar_color is not None:
        user.avatar_color = body.avatar_color
    if body.role is not None and is_admin:
        user.role = UserRole(body.role)
    if body.password is not None:
        # Only admins can change other users' passwords
        if is_self or is_admin:
            user.hashed_password = get_password_hash(body.password)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins can change other users' passwords"
            )

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}/deactivate")
async def deactivate_member(
    user_id: int,
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


@router.patch("/{user_id}/activate")
async def activate_member(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Reactivate a deactivated team member."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = True
    await db.commit()
    return {"id": str(user.id), "is_active": True}
