"""Backlog category endpoints (2026-09-28 — categories per project).

GET    /projects/{id}/backlog-categories              — the project's categories (tech roles)
POST   /projects/{id}/backlog-categories              — add one (CTO/Admin)
PATCH  /projects/{id}/backlog-categories/{cid}        — rename / restyle (not Default)
PUT    /projects/{id}/backlog-categories/order        — reorder every non-Default category
DELETE /projects/{id}/backlog-categories/{cid}        — delete; its items move to Default

Rules live in ``app/services/backlog_category_service.py``.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import policy
from app.core.auth import get_current_user
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import get_db
from app.policy import Action
from app.schemas.backlog_category import (
    BacklogCategoryCreate,
    BacklogCategoryDeleted,
    BacklogCategoryList,
    BacklogCategoryOrder,
    BacklogCategoryOut,
    BacklogCategoryUpdate,
    BacklogCategoryWithCount,
)
from app.services.authz import actor_of, authorize, project_target
from app.services.backlog_category_service import backlog_category_service

router = APIRouter()


async def _project(db: AsyncSession, project_id: int) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _listing(db: AsyncSession, project: Project, user: User) -> BacklogCategoryList:
    rows = await backlog_category_service.list_with_counts(db, project.id)
    return BacklogCategoryList(
        project_id=project.id,
        categories=[
            BacklogCategoryWithCount(
                **BacklogCategoryOut.model_validate(c).model_dump(), item_count=n,
            )
            for c, n in rows
        ],
        can_manage=policy.allows(actor_of(user), Action.manage_backlog_categories),
    )


@router.get(
    "/{project_id}/backlog-categories",
    response_model=BacklogCategoryList,
    summary="List a project's backlog categories",
)
async def list_categories(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BacklogCategoryList:
    project = await _project(db, project_id)
    authorize(current_user, Action.view_backlog, project_target(project))
    return await _listing(db, project, current_user)


@router.post(
    "/{project_id}/backlog-categories",
    response_model=BacklogCategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add a backlog category",
)
async def create_category(
    project_id: int,
    payload: BacklogCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BacklogCategoryOut:
    project = await _project(db, project_id)
    authorize(current_user, Action.manage_backlog_categories, project_target(project))
    category = await backlog_category_service.create(
        db, project, name=payload.name, icon=payload.icon, color=payload.color,
    )
    await db.commit()
    return BacklogCategoryOut.model_validate(category)


@router.put(
    "/{project_id}/backlog-categories/order",
    response_model=BacklogCategoryList,
    summary="Reorder backlog categories",
)
async def reorder_categories(
    project_id: int,
    payload: BacklogCategoryOrder,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BacklogCategoryList:
    project = await _project(db, project_id)
    authorize(current_user, Action.manage_backlog_categories, project_target(project))
    await backlog_category_service.reorder(db, project, payload.ids)
    await db.commit()
    return await _listing(db, project, current_user)


@router.patch(
    "/{project_id}/backlog-categories/{category_id}",
    response_model=BacklogCategoryOut,
    summary="Rename or restyle a backlog category",
)
async def update_category(
    project_id: int,
    category_id: int,
    payload: BacklogCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BacklogCategoryOut:
    project = await _project(db, project_id)
    authorize(current_user, Action.manage_backlog_categories, project_target(project))
    category = await backlog_category_service.update(
        db, project, category_id, payload.model_dump(exclude_unset=True),
    )
    await db.commit()
    return BacklogCategoryOut.model_validate(category)


@router.delete(
    "/{project_id}/backlog-categories/{category_id}",
    response_model=BacklogCategoryDeleted,
    summary="Delete a backlog category (its items move to Default)",
)
async def delete_category(
    project_id: int,
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BacklogCategoryDeleted:
    project = await _project(db, project_id)
    authorize(current_user, Action.manage_backlog_categories, project_target(project))
    moved = await backlog_category_service.delete(db, project, category_id, current_user)
    default = await backlog_category_service.default_for(db, project.id)
    await db.commit()
    return BacklogCategoryDeleted(
        moved_count=moved, default_category=BacklogCategoryOut.model_validate(default),
    )
