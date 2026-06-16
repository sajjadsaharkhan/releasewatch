"""Public user profile endpoints.

GET /users/by-username/{username}  — user profile + computed stats
GET /users/{user_id}/activity      — monthly reported/fixed counts for current year
"""

from calendar import month_abbr
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.issue import Issue, IssueStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.user import ActivityDataPoint, UserProfileResponse

router = APIRouter()

_FIXED_STATUSES = {IssueStatus.fixed, IssueStatus.verified}


async def _build_profile(user: User, db: AsyncSession) -> UserProfileResponse:
    """Compute issue stats and build a UserProfileResponse for the given user."""
    reported_count = (
        await db.execute(select(func.count(Issue.id)).where(Issue.reporter_id == user.id))
    ).scalar_one()

    assigned_q = select(func.count(Issue.id)).where(Issue.assignee_id == user.id)
    assigned_count = (await db.execute(assigned_q)).scalar_one()

    fixed_count = (
        await db.execute(
            select(func.count(Issue.id)).where(
                Issue.assignee_id == user.id,
                Issue.status.in_(_FIXED_STATUSES),
            )
        )
    ).scalar_one()

    fix_rate = round(fixed_count / assigned_count * 100) if assigned_count > 0 else None

    return UserProfileResponse(
        id=user.id,
        name=user.name,
        username=user.username,
        role=user.role,
        title=user.title,
        bio=user.bio,
        avatar_url=user.avatar_url,
        avatar_color=user.avatar_color,
        is_active=user.is_active,
        joinedAt=user.created_at.isoformat() if user.created_at else None,
        tgConnected=user.telegram_handle is not None,
        tgHandle=user.telegram_handle,
        reported=reported_count,
        fixed=fixed_count,
        fixRate=fix_rate,
        regressionRate=0,
        mtt=None,
        mtv=None,
        mtf=None,
    )


@router.get("/users/by-username/{username}", response_model=UserProfileResponse)
async def get_user_by_username(
    username: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserProfileResponse:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return await _build_profile(user, db)


@router.get("/users/{user_id}/activity", response_model=list[ActivityDataPoint])
async def get_user_activity(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActivityDataPoint]:
    """Return monthly reported/fixed counts for the current calendar year."""
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    year = datetime.now(tz=timezone.utc).year

    reported_rows = (
        await db.execute(
            select(
                extract("month", Issue.created_at).label("month"),
                func.count(Issue.id).label("cnt"),
            )
            .where(Issue.reporter_id == user_id)
            .where(extract("year", Issue.created_at) == year)
            .group_by(extract("month", Issue.created_at))
        )
    ).all()

    fixed_rows = (
        await db.execute(
            select(
                extract("month", Issue.updated_at).label("month"),
                func.count(Issue.id).label("cnt"),
            )
            .where(Issue.assignee_id == user_id)
            .where(Issue.status.in_(_FIXED_STATUSES))
            .where(extract("year", Issue.updated_at) == year)
            .group_by(extract("month", Issue.updated_at))
        )
    ).all()

    reported_map = {int(r.month): r.cnt for r in reported_rows}
    fixed_map = {int(r.month): r.cnt for r in fixed_rows}

    return [
        ActivityDataPoint(
            month=month_abbr[m],
            reported=reported_map.get(m, 0),
            fixed=fixed_map.get(m, 0),
        )
        for m in range(1, 13)
    ]
