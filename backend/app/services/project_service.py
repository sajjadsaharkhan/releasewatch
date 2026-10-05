"""ProjectService — domain rules for projects.

Permissions live in ``app/policy.py``; the data-integrity side (triage lead
rules BR-15/AC-23) lives here. Every project's Stream is created with it by an
ORM hook (``app/db/models/release.py``), so every writer gets one (BR-51).
"""

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.models.project import Project
from app.db.models.user import User
from app.policy import is_tech


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
            "The triage lead must be an active QA, Developer, Product Manager, CTO, or Admin user.",
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
