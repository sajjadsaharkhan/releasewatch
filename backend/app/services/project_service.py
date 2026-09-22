"""ProjectService — domain rules for projects.

Kept the BR-02 guard out of the route layer (CLAUDE.md: thin routes,
services own state transitions). Slice 04's Policy module will absorb the
permission side; the data-integrity side lives here.
"""

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.models.project import Project, ProjectKind
from app.db.models.release import Release


async def guard_kind_change(db: AsyncSession, project: Project, update_data: dict) -> None:
    """Refuse moving a Product project off Product while it still has releases (BR-02).

    ``update_data`` is the PATCH payload as a dict (``exclude_unset=True``);
    a payload without ``kind`` passes untouched.
    """
    if "kind" not in update_data:
        return
    old_kind = getattr(project.kind, "value", project.kind)
    new_kind = getattr(update_data["kind"], "value", update_data["kind"])
    if old_kind != ProjectKind.product.value or new_kind == ProjectKind.product.value:
        return
    count_result = await db.execute(
        select(func.count(Release.id)).where(Release.project_id == project.id)
    )
    if count_result.scalar_one() > 0:
        raise DomainError(
            status.HTTP_409_CONFLICT,
            "Cannot change kind while the project still has releases.",
            "project_has_releases",
        )
