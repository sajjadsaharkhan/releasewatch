"""Backlog and Technical debt endpoints (slice 08, FR-23–29).

GET  /projects/{id}/backlog?include_tech_debt=&group_by=category — the ranked backlog
PUT  /projects/{id}/backlog/order                                — drag-rank one item
POST /projects/{id}/backlog/category                             — set several items' category
GET  /tech-debt?project_id=1,2&status=&assignee_id=               — flagged tasks, any project

Membership and ranking live in ``app/services/backlog_service.py``; these
routes only authorize and shape responses. ``POST /issues/bulk-move`` is in
``issues.py`` with the other item actions.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import policy
from app.core.auth import get_current_user
from app.core.clock import get_now
from app.db.models.backlog_category import BacklogCategory
from app.db.models.issue import Issue
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import get_db
from app.policy import Action
from app.schemas.backlog import (
    BacklogCategoryRequest,
    BacklogCategoryResponse,
    BacklogGroup,
    BacklogOrderRequest,
    BacklogOrderResponse,
    BacklogResponse,
    TechDebtListResponse,
)
from app.schemas.backlog_category import BacklogCategoryOut
from app.schemas.issue import BlockedAction
from app.services.authz import actor_of, authorize, project_target, visibility_clause
from app.services.backlog_category_service import backlog_category_service
from app.services.backlog_service import backlog_service, tech_debt_clause

router = APIRouter()

TECH_DEBT_GROUP = "tech_debt"


async def _project_or_404(db: AsyncSession, project_id: int) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _groups(items: list[Issue], categories: list[BacklogCategory]) -> list[BacklogGroup]:
    """One group per project category in its order (Default first, empty ones
    included), then Technical debt — every debt task, whatever its category (FR-24)."""
    buckets: dict[int, list[int]] = {c.id: [] for c in categories}
    debt: list[int] = []
    for issue in items:
        if issue.is_tech_debt:
            debt.append(issue.id)
        else:
            buckets.setdefault(issue.backlog_category_id, []).append(issue.id)
    groups = [
        BacklogGroup(
            key=str(c.id), category=BacklogCategoryOut.model_validate(c),
            count=len(buckets[c.id]), item_ids=buckets[c.id],
        )
        for c in categories
    ]
    if debt:
        groups.append(BacklogGroup(key=TECH_DEBT_GROUP, count=len(debt), item_ids=debt))
    return groups


@router.get(
    "/projects/{project_id}/backlog", response_model=BacklogResponse, summary="Project backlog",
)
async def get_backlog(
    project_id: int,
    include_tech_debt: bool = Query(False, description="Show technical-debt tasks (FR-24)."),
    group_by: str | None = Query(None, pattern="^category$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> BacklogResponse:
    """Open items with no release, ranked (BR-04). Technical debt hidden by default."""
    from app.api.v1.issues import _build_enriched_responses

    project = await _project_or_404(db, project_id)
    authorize(current_user, Action.view_backlog, project_target(project))

    page = await backlog_service.page(
        db, project_id, include_tech_debt=include_tech_debt, now=now,
    )
    manage = policy.decide(actor_of(current_user), Action.manage_backlog, project_target(project))
    return BacklogResponse(
        project_id=project_id,
        items=await _build_enriched_responses(page.items, db, current_user),
        total=len(page.items),
        stale_count=len(page.stale_ids),
        stale_item_ids=page.stale_ids,
        hidden_tech_debt_count=page.hidden_tech_debt_count,
        groups=(
            _groups(page.items, await backlog_category_service.ordered(db, project_id))
            if group_by == "category" else None
        ),
        allowed_actions=[Action.manage_backlog.value] if manage.ok else [],
        blocked_actions=(
            [] if manage.ok or manage.hidden
            else [BlockedAction(
                action=Action.manage_backlog.value, code=manage.code, detail=manage.detail,
            )]
        ),
    )


@router.put(
    "/projects/{project_id}/backlog/order",
    response_model=BacklogOrderResponse,
    summary="Rank a backlog item",
)
async def reorder_backlog(
    project_id: int,
    payload: BacklogOrderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BacklogOrderResponse:
    """Place one item between its new neighbours (FR-25). ``manage_backlog`` only."""
    project = await _project_or_404(db, project_id)
    authorize(current_user, Action.manage_backlog, project_target(project))
    rank = await backlog_service.reorder(
        db, project, payload.issue_id, before_id=payload.before_id, after_id=payload.after_id,
    )
    await db.commit()
    return BacklogOrderResponse(issue_id=payload.issue_id, backlog_rank=rank)


@router.post(
    "/projects/{project_id}/backlog/category",
    response_model=BacklogCategoryResponse,
    summary="Set the category of several backlog items",
)
async def set_backlog_category(
    project_id: int,
    payload: BacklogCategoryRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BacklogCategoryResponse:
    """Move a multi-selection to another category group, all or nothing.

    ``manage_backlog`` on the project; every item must be in it (409
    ``bulk_category_failed`` lists the ones that aren't).
    """
    from app.api.v1.issues import _build_enriched_responses

    project = await _project_or_404(db, project_id)
    authorize(current_user, Action.manage_backlog, project_target(project))

    ids = list(dict.fromkeys(payload.issue_ids))
    rows = (await db.execute(
        select(Issue).where(
            Issue.id.in_(ids), Issue.deleted_at.is_(None), visibility_clause(current_user),
        ).with_for_update()
    )).scalars().all()
    found = {i.id: i for i in rows}
    category = await backlog_category_service.resolve(db, project.id, payload.backlog_category_id)
    updated = await backlog_service.bulk_set_category(
        db, project, {i: found.get(i) for i in ids}, category, current_user,
    )
    await db.commit()

    result = await db.execute(
        select(Issue).options(
            selectinload(Issue.assignee),
            selectinload(Issue.reporter),
            selectinload(Issue.release),
            selectinload(Issue.project),
        ).where(Issue.id.in_(ids))
    )
    by_id = {i.id: i for i in result.scalars().all()}
    items = await _build_enriched_responses([by_id[i] for i in ids], db, current_user)
    return BacklogCategoryResponse(updated_ids=updated, items=items)


def _int_list(raw: str | None, name: str) -> list[int]:
    if not raw:
        return []
    try:
        return [int(part) for part in raw.split(",") if part.strip()]
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{name} must be a comma-separated list of ids.",
        ) from err


@router.get("/tech-debt", response_model=TechDebtListResponse, summary="Technical debt")
async def list_tech_debt(
    project_id: str | None = Query(None, description="Comma-separated project ids, e.g. 1,2"),
    status_: str | None = Query(None, alias="status", description="Comma-separated statuses"),
    assignee_id: int | None = Query(None),
    unassigned: bool | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TechDebtListResponse:
    """Every technical-debt task, across projects (FR-27). Highest priority first, then oldest."""
    from app.api.v1.issues import _PRIORITY_ORDER, _build_enriched_responses, _parse_statuses

    authorize(current_user, Action.view_backlog)
    project_ids = _int_list(project_id, "project_id")
    statuses = _parse_statuses(status_)

    filters = [tech_debt_clause(), visibility_clause(current_user)]
    if project_ids:
        filters.append(Issue.project_id.in_(project_ids))
    if statuses:
        filters.append(Issue.status.in_([s.value for s in statuses]))
    if assignee_id is not None:
        filters.append(Issue.assignee_id == assignee_id)
    if unassigned:
        filters.append(Issue.assignee_id.is_(None))

    total = (await db.execute(select(func.count(Issue.id)).where(*filters))).scalar_one()
    rows = (await db.execute(
        select(Issue)
        .options(
            selectinload(Issue.assignee),
            selectinload(Issue.reporter),
            selectinload(Issue.release),
            selectinload(Issue.project),
        )
        .where(*filters)
        .order_by(_PRIORITY_ORDER, Issue.created_at.asc(), Issue.id.asc())
        .offset((page - 1) * size)
        .limit(size)
    )).scalars().all()
    return TechDebtListResponse(
        items=await _build_enriched_responses(list(rows), db, current_user),
        total=total,
    )
