"""Support intake endpoints (slice 05).

GET  /support/projects                   — projects with at least one active template
GET  /support/projects/{id}/templates    — a project's active templates, with fields
POST /support/reports                    — submit a report (→ New bug, source support)
GET  /support/reports                    — every support-sourced item the caller can see

Thin routes: ``SupportService`` owns the rules. See docs/phase-2/05-support-intake.md.
"""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.issue import IssueStatus
from app.db.models.user import User
from app.db.session import get_db
from app.policy import Action
from app.schemas.support import (
    SupportProject,
    SupportReportCreate,
    SupportReportList,
    SupportReportRow,
    TemplateResponse,
)
from app.services.authz import require_action
from app.services.support_service import load_report, report_row, support_service

router = APIRouter()


@router.get(
    "/projects", response_model=list[SupportProject], summary="Projects Support can report on",
)
async def list_reportable_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.submit_support_report)),
) -> list[SupportProject]:
    projects = await support_service.reportable_projects(db)
    return [SupportProject.model_validate(p) for p in projects]


@router.get(
    "/projects/{project_id}/templates",
    response_model=list[TemplateResponse],
    summary="A project's active support templates",
)
async def list_project_templates(
    project_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.submit_support_report)),
) -> list[TemplateResponse]:
    templates = await support_service.active_templates(db, project_id)
    return [TemplateResponse.model_validate(t) for t in templates]


@router.post(
    "/reports",
    response_model=SupportReportRow,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a support report",
)
async def submit_report(
    payload: SupportReportCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.submit_support_report)),
) -> SupportReportRow:
    issue = await support_service.submit(db, payload, current_user)
    await db.commit()

    from app.tasks.search import embed_issue
    embed_issue.apply_async((issue.id,), countdown=0)
    return report_row(await load_report(db, issue.id))


@router.get("/reports", response_model=SupportReportList, summary="Support reports list")
async def list_reports(
    q: str | None = Query(None, description="Search title, description, or number"),
    project_id: int | None = Query(None),
    status_: list[IssueStatus] | None = Query(None, alias="status"),
    reporter_id: int | None = Query(None, description="Only reports filed by this user (the list's \"Me\" filter)"),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SupportReportList:
    return await support_service.list_reports(
        db, current_user, q=q, project_id=project_id, statuses=status_, reporter_id=reporter_id,
        page=page, size=size,
    )
