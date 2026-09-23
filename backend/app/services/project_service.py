"""ProjectService — domain rules for projects.

Kept the BR-02 guard out of the route layer (CLAUDE.md: thin routes,
services own state transitions). Permissions live in ``app/policy.py``; the
data-integrity side (release/kind guard, triage lead rules BR-15/AC-23) lives here.
"""

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.models.project import Project, ProjectKind
from app.db.models.release import Release
from app.db.models.user import User
from app.policy import is_tech


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


async def validate_triage_lead(db: AsyncSession, triage_lead_id: int | None) -> None:
    """BR-15 — a project's triage lead must be an active tech-role user (422 otherwise).

    Called on create (where the lead is required) and on any update that
    touches ``triage_lead_id`` (where clearing it is refused too). Existing
    projects that already lack a lead stay as they are, flagged via
    ``project_needs_triage_lead``.
    """
    if triage_lead_id is None:
        raise DomainError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Every project needs a triage lead.",
            "triage_lead_required",
        )
    user = await db.get(User, triage_lead_id)
    if user is None or not user.is_active or not is_tech(user.role):
        raise DomainError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "The triage lead must be an active QA, Developer, PM, CTO, or Admin user.",
            "invalid_triage_lead",
        )


async def project_needs_triage_lead(db: AsyncSession, project: Project) -> bool:
    """AC-23 — true when the project's lead is unset, deactivated, or no longer a tech role."""
    if project.triage_lead_id is None:
        return True
    user = await db.get(User, project.triage_lead_id)
    return user is None or not user.is_active or not is_tech(user.role)


async def projects_led_by(db: AsyncSession, user_id: int) -> list[Project]:
    """Active projects whose triage lead is ``user_id`` — what deactivating them would orphan."""
    result = await db.execute(
        select(Project)
        .where(Project.triage_lead_id == user_id, Project.archived_at.is_(None))
        .order_by(Project.name)
    )
    return list(result.scalars().all())
