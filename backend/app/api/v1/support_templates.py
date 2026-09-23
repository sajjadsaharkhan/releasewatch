"""Support template admin endpoints (slice 05, FR-44) — CTO and Admin (``manage_templates``).

GET    /projects/{id}/templates                        — every template, inactive included
POST   /projects/{id}/templates                        — create (optionally with fields)
PATCH  /projects/{id}/templates/{tid}                  — rename
PUT    /projects/{id}/templates/{tid}/fields           — replace the ordered field list
POST   /projects/{id}/templates/{tid}/activate         — reactivate
POST   /projects/{id}/templates/{tid}/deactivate       — retire without deleting history

No DELETE: a template is retired, never removed (FR-44). Editing or
deactivating one never changes existing reports (FR-45, BR-35).
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.db.session import get_db
from app.policy import Action
from app.schemas.support import TemplateCreate, TemplateFieldIn, TemplateResponse, TemplateUpdate
from app.services.authz import require_action
from app.services.support_service import support_service

router = APIRouter()

_manager = require_action(Action.manage_templates)


async def _fresh(db: AsyncSession, project_id: int, template_id: int) -> TemplateResponse:
    """Re-read after commit so the response carries the saved fields."""
    template = await support_service.get_template(db, project_id, template_id)
    return TemplateResponse.model_validate(template)


@router.get(
    "/{project_id}/templates", response_model=list[TemplateResponse], summary="List templates",
)
async def list_templates(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_manager),
) -> list[TemplateResponse]:
    templates = await support_service.list_templates(db, project_id)
    return [TemplateResponse.model_validate(t) for t in templates]


@router.post(
    "/{project_id}/templates",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a template",
)
async def create_template(
    project_id: int,
    payload: TemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_manager),
) -> TemplateResponse:
    template = await support_service.create_template(db, project_id, payload, current_user)
    await db.commit()
    return await _fresh(db, project_id, template.id)


@router.patch(
    "/{project_id}/templates/{template_id}",
    response_model=TemplateResponse,
    summary="Rename a template",
)
async def rename_template(
    project_id: int,
    template_id: int,
    payload: TemplateUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_manager),
) -> TemplateResponse:
    await support_service.rename_template(db, project_id, template_id, payload.name)
    await db.commit()
    return await _fresh(db, project_id, template_id)


@router.put(
    "/{project_id}/templates/{template_id}/fields",
    response_model=TemplateResponse,
    summary="Replace a template's fields",
)
async def replace_fields(
    project_id: int,
    template_id: int,
    payload: list[TemplateFieldIn],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_manager),
) -> TemplateResponse:
    await support_service.replace_fields(db, project_id, template_id, payload)
    await db.commit()
    return await _fresh(db, project_id, template_id)


async def _set_active(
    db: AsyncSession, project_id: int, template_id: int, active: bool,
) -> TemplateResponse:
    await support_service.set_active(db, project_id, template_id, active)
    await db.commit()
    return await _fresh(db, project_id, template_id)


@router.post(
    "/{project_id}/templates/{template_id}/activate",
    response_model=TemplateResponse,
    summary="Reactivate a template",
)
async def activate_template(
    project_id: int,
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_manager),
) -> TemplateResponse:
    return await _set_active(db, project_id, template_id, True)


@router.post(
    "/{project_id}/templates/{template_id}/deactivate",
    response_model=TemplateResponse,
    summary="Deactivate a template",
)
async def deactivate_template(
    project_id: int,
    template_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_manager),
) -> TemplateResponse:
    return await _set_active(db, project_id, template_id, False)
