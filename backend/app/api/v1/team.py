"""Team management API — list members, invite, change role, deactivate.

User management is Admin and CTO (``manage_users``, §7.3). ``GET /team?assignable=true``
is what every assignee picker calls — it never lists Support users (BR-32, AC-47).
``GET /team/workload`` is the Team overview's Workload view (slice 11, FR-43) —
CTO and Admin only (``view_team_overview``, AC-48).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, get_password_hash
from app.core.clock import get_now
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.policy import ASSIGNABLE_ROLES, Action
from app.schemas.queue import WorkloadRow
from app.schemas.team import (
    ChangeRoleRequest,
    InviteRequest,
    MemberResponse,
    TeamMemberResponse,
    UserUpdateRequest,
)
from app.schemas.user import UserResponse
from app.services.authz import require_action
from app.services.project_service import projects_led_by
from app.services.queue_service import queue_service

router = APIRouter()


@router.get("", response_model=list[MemberResponse])
async def list_team(
    assignable: bool = Query(False, description="Only users who can be assigned work (no Support)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all active team members with Telegram connection status."""
    query = (
        select(User)
        .options(selectinload(User.telegram_integration))
        .where(User.is_active == True)
        .order_by(User.is_active.desc(), User.name)
    )
    if assignable:
        query = query.where(User.role.in_(sorted(ASSIGNABLE_ROLES)))
    result = await db.execute(query)
    users = result.scalars().all()

    return [
        MemberResponse(
            id=user.id,
            name=user.name,
            username=user.username,
            role=user.role,
            avatar_url=user.avatar_url,
            avatar_color=user.avatar_color,
            is_active=user.is_active,
            created_at=user.created_at,
            title=user.title,
            bio=user.bio,
            tgConnected=user.telegram_integration is not None and user.telegram_integration.is_active,
            tgHandle=user.telegram_integration.telegram_username if user.telegram_integration else None,
            reported=0,
            fixed=0,
            avgFixTime=None,
            fixRate=None,
        )
        for user in users
    ]


@router.get("/workload", response_model=list[WorkloadRow], summary="Team workload")
async def workload(
    role: UserRole | None = Query(None, description="Only people with this role"),
    project_id: int | None = Query(None, description="Only people with open work in this project"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.view_team_overview)),
    now: datetime = Depends(get_now),
) -> list[WorkloadRow]:
    """Each active assignable user's In progress items, next three queue items,
    and open/pinned counts, in name order."""
    return await queue_service.workload(
        db, now, role=role.value if role else None, project_id=project_id,
    )


@router.get("/all", response_model=list[MemberResponse])
async def list_all_team(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all team members including inactive ones (for Settings page)."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.telegram_integration))
        .order_by(User.is_active.desc(), User.name)
    )
    users = result.scalars().all()

    return [
        MemberResponse(
            id=user.id,
            name=user.name,
            username=user.username,
            role=user.role,
            avatar_url=user.avatar_url,
            avatar_color=user.avatar_color,
            is_active=user.is_active,
            created_at=user.created_at,
            title=user.title,
            bio=user.bio,
            tgConnected=user.telegram_integration is not None and user.telegram_integration.is_active,
            tgHandle=user.telegram_integration.telegram_username if user.telegram_integration else None,
            reported=0,
            fixed=0,
            avgFixTime=None,
            fixRate=None,
        )
        for user in users
    ]


@router.post("/invite", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    body: InviteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.manage_users)),
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
        is_active=user.is_active,
        created_at=user.created_at,
        title=user.title,
        bio=user.bio,
        tgConnected=False,
        tgHandle=None,
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
    current_user: User = Depends(require_action(Action.manage_users)),
):
    """Change a team member's role (Admin and CTO)."""
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
    Admins and CTOs can edit anyone. Users can edit their own profile (except role).
    Password changes only allowed by admins or for self.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Only admins and CTOs can change role and password of others
    is_admin = current_user.role in (UserRole.admin, UserRole.cto)  # CTO = Admin here
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
        # Only admins and CTOs can change other users' passwords
        if is_self or is_admin:
            user.hashed_password = get_password_hash(body.password)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admins and CTOs can change other users' passwords"
            )

    await db.commit()
    await db.refresh(user)
    return UserResponse.model_validate(user)


@router.patch("/{user_id}/deactivate")
async def deactivate_member(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.manage_users)),
):
    """Soft-deactivate a team member — they keep history but cannot log in."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot deactivate yourself")
    affected = await projects_led_by(db, user.id)
    user.is_active = False
    await db.commit()
    return {
        "id": str(user.id),
        "is_active": False,
        # These projects now need a new triage lead (AC-23); admins get their triage mail meanwhile.
        "affected_projects": [_project_ref(p) for p in affected],
    }


@router.get("/{user_id}/deactivation-impact")
async def deactivation_impact(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.manage_users)),
):
    """What deactivating this user would orphan — for the confirmation dialog."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"affected_projects": [_project_ref(p) for p in await projects_led_by(db, user_id)]}


def _project_ref(project) -> dict:
    return {"id": project.id, "name": project.name, "slug": project.slug}


@router.patch("/{user_id}/activate")
async def activate_member(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.manage_users)),
):
    """Reactivate a deactivated team member."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.is_active = True
    await db.commit()
    return {"id": str(user.id), "is_active": True}
