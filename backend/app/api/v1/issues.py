"""Issue endpoints.

GET    /issues                              — list issues (filters + sort handled server-side)
GET    /issues/export                       — export issues as CSV
GET    /issues/trash                        — list soft-deleted issues (CTO/admin only)
DELETE /issues/trash/clear                  — permanently delete all trashed issues (CTO/admin only)
POST   /issues                             — file a new issue
GET    /issues/{id}                         — get issue detail
PATCH  /issues/{id}                         — update issue fields
DELETE /issues/{id}                         — delete issue (CTO, admin, reporter, or triage lead)
POST   /issues/{id}/restore                 — restore a soft-deleted issue (CTO/admin only)
DELETE /issues/{id}/permanent               — permanently delete one trashed issue (CTO/admin only)
POST   /issues/{id}/triage                  — triage an issue (new -> todo)
POST   /issues/{id}/needs-clarification     — request clarification (new -> needs_info)
POST   /issues/{id}/fix                     — mark as fixed (-> in_review)
POST   /issues/{id}/verify                  — verify the fix (in_review -> done | in_progress)
POST   /issues/{id}/reopen                  — reopen a Done bug (maps to the regression action)
POST   /issues/{id}/duplicate               — link as duplicate (-> cancelled, reason duplicate)
POST   /issues/{id}/transition              — generic status change; used by board drags and menus
POST   /issues/{id}/regression              — flag a regression on a Done/In review bug (BR-24)
GET    /issues/by-number/{n}/adjacent       — prev/next non-deleted issue numbers

Every status change goes through ``IssueService.transition()``
(``app/workflow.py`` decides what's allowed) — see
docs/phase-2/02-unified-status-model.md.
"""

import csv
import io
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, require_role
from app.db.models.issue import (
    Issue, IssueSeverity, IssueStatus, IssueType, issue_key, issue_type_value,
)
from app.db.models.issue_cycle import IssueCycle
from app.db.models.label import Label
from app.db.models.project import Project, ProjectKind
from app.db.models.regression_history import RegressionHistory
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.issue import (
    BlockedTransition,
    DuplicateRequest,
    FixRequest,
    IssueCreate,
    IssueCycleResponse,
    IssueListResponse,
    IssueResponse,
    IssueUpdate,
    LabelDetail,
    NeedsClarificationRequest,
    RegressionHistoryResponse,
    TransitionRequest,
    TrashIssueResponse,
    TriageRequest,
    UserSummary,
    VerifyRequest,
)
from app.services.issue_service import issue_service
from app.workflow import Workflow

router = APIRouter()

_SEVERITY_ORDER = case(
    (Issue.severity == IssueSeverity.blocker, 0),
    (Issue.severity == IssueSeverity.critical, 1),
    (Issue.severity == IssueSeverity.major, 2),
    (Issue.severity == IssueSeverity.minor, 3),
    else_=4,
)


def _parse_statuses(raw: str | None) -> list[IssueStatus] | None:
    """Parse a comma-separated `statuses` query value into enum members.

    Lets a client filter on a set of states (e.g. the "Open issues" view) without
    turning the single-value `status` filter into a list and breaking its callers.
    """
    if not raw:
        return None
    parsed: list[IssueStatus] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            parsed.append(IssueStatus(part))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status: {part}",
            )
    return parsed or None


def _apply_filters(
    query,
    *,
    project_id,
    release_id,
    status,
    statuses=None,
    severity,
    assignee_id,
    reporter_id=None,
    is_regression,
    is_release_blocker,
    unassigned,
    labels,
    search,
    type=None,
    is_urgent=None,
    has_release=None,
    project_kind=None,
):
    query = query.where(Issue.deleted_at.is_(None))
    if project_id:
        query = query.where(Issue.project_id == project_id)
    if release_id:
        query = query.where(Issue.release_id == release_id)
    if status:
        query = query.where(Issue.status == status)
    if statuses:
        query = query.where(Issue.status.in_(statuses))
    if severity:
        query = query.where(Issue.severity == severity)
    if assignee_id:
        query = query.where(Issue.assignee_id == assignee_id)
    if reporter_id:
        query = query.where(Issue.reporter_id == reporter_id)
    if is_regression is not None:
        query = query.where(Issue.is_regression == is_regression)
    if is_release_blocker is not None:
        query = query.where(Issue.is_release_blocker == is_release_blocker)
    if unassigned:
        query = query.where(Issue.assignee_id.is_(None))
    if labels:
        query = query.where(or_(*[Issue.labels.any(name) for name in labels]))
    if type:
        query = query.where(Issue.type == type)
    if is_urgent is not None:
        query = query.where(Issue.is_urgent == is_urgent)
    if has_release is not None:
        query = query.where(Issue.release_id.isnot(None) if has_release else Issue.release_id.is_(None))
    if project_kind:
        query = query.where(
            Issue.project_id.in_(select(Project.id).where(Project.kind == project_kind))
        )
    if search:
        from sqlalchemy import String as SAString
        from sqlalchemy import cast
        query = query.where(
            or_(
                Issue.title.ilike(f"%{search}%"),
                cast(Issue.issue_number, SAString).ilike(f"%{search}%"),
            )
        )
    return query


def _apply_sort(query, sort: str):
    if sort == "oldest":
        return query.order_by(Issue.created_at.asc(), Issue.issue_number.asc())
    elif sort == "severity":
        return query.order_by(_SEVERITY_ORDER, Issue.created_at.desc(), Issue.issue_number.desc())
    elif sort == "updated":
        return query.order_by(Issue.updated_at.desc(), Issue.issue_number.desc())
    else:
        return query.order_by(Issue.created_at.desc(), Issue.issue_number.desc())


def _workflow_fields(issue: Issue, current_user: User) -> dict:
    """Compute allowed_transitions / blocked_transitions for one issue."""
    release = issue.release
    context = {
        "actor_id": current_user.id,
        "review_requested_by_id": issue.review_requested_by_id,
        "blocked_from_status": issue.blocked_from_status,
        "has_release": issue.release_id is not None,
        "release_shipped": release.is_shipped if release is not None else False,
    }
    item_type = issue_type_value(issue.type)
    targets = Workflow.allowed_targets(item_type, issue.status, context)
    return {
        "allowed_transitions": targets.allowed,
        "blocked_transitions": [BlockedTransition(**b) for b in targets.blocked],
    }


async def _reload_and_enrich(db: AsyncSession, issue_id: int, current_user: User) -> IssueResponse:
    """Re-fetch an issue with its relations after a service call and enrich it.

    Used by every action endpoint (``/triage``, ``/fix``, ``/transition``, …)
    so the response always carries ``allowed_transitions`` for the next click.
    """
    result = await db.execute(
        select(Issue).options(
            selectinload(Issue.assignee),
            selectinload(Issue.reporter),
            selectinload(Issue.release),
            selectinload(Issue.project),
        ).where(Issue.id == issue_id)
    )
    issue = result.scalar_one()
    enriched = await _build_enriched_responses([issue], db, current_user)
    return enriched[0]


async def _build_enriched_responses(
    issues: list[Issue], db: AsyncSession, current_user: User
) -> list[IssueResponse]:
    """Build IssueResponse objects with embedded user/label/release data."""
    all_label_names = {name for issue in issues for name in (issue.labels or [])}
    label_map: dict[str, Label] = {}
    if all_label_names:
        result = await db.execute(select(Label).where(Label.name.in_(all_label_names)))
        for label in result.scalars().all():
            label_map[label.name] = label

    responses = []
    for issue in issues:
        resp = IssueResponse.model_validate(issue)
        enriched = resp.model_copy(update={
            "assignee_user": (
                UserSummary.model_validate(issue.assignee) if issue.assignee else None
            ),
            "reporter_user": (
                UserSummary.model_validate(issue.reporter) if issue.reporter else None
            ),
            "labels_detail": [
                LabelDetail(id=label_map[n].id, name=n, color=label_map[n].color)
                for n in (issue.labels or [])
                if n in label_map
            ],
            "release_version": issue.release.version if issue.release else None,
            "project_triage_lead_id": issue.project.triage_lead_id if issue.project else None,
            "project_name": issue.project.name if issue.project else None,
            **_workflow_fields(issue, current_user),
        })
        responses.append(enriched)
    return responses


@router.get("", response_model=IssueListResponse, summary="List issues")
async def list_issues(
    project_id: int | None = Query(None),
    release_id: int | None = Query(None),
    status: IssueStatus | None = Query(None),
    statuses: str | None = Query(
        None, description="Comma-separated statuses, e.g. new,triaged,in_progress"
    ),
    severity: IssueSeverity | None = Query(None),
    assignee_id: int | None = Query(None),
    reporter_id: int | None = Query(None),
    is_regression: bool | None = Query(None),
    is_release_blocker: bool | None = Query(None),
    unassigned: bool | None = Query(None),
    labels: list[str] | None = Query(None),
    sort: str = Query("newest"),
    search: str | None = Query(None),
    type: IssueType | None = Query(None),
    is_urgent: bool | None = Query(None),
    has_release: bool | None = Query(None, description="True: has a release. False: hotfix/task with no release."),
    project_kind: ProjectKind | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueListResponse:
    """Return a paginated, filterable, sortable list of issues."""
    filter_kwargs = dict(
        project_id=project_id,
        release_id=release_id,
        status=status,
        statuses=_parse_statuses(statuses),
        severity=severity,
        assignee_id=assignee_id,
        reporter_id=reporter_id,
        is_regression=is_regression,
        is_release_blocker=is_release_blocker,
        unassigned=unassigned,
        labels=labels,
        search=search,
        type=type,
        is_urgent=is_urgent,
        has_release=has_release,
        project_kind=project_kind,
    )

    count_q = _apply_filters(select(func.count(Issue.id)), **filter_kwargs)
    total = (await db.execute(count_q)).scalar_one()

    fetch_q = select(Issue).options(
        selectinload(Issue.assignee),
        selectinload(Issue.reporter),
        selectinload(Issue.release),
        selectinload(Issue.project),
    )
    fetch_q = _apply_filters(fetch_q, **filter_kwargs)
    fetch_q = _apply_sort(fetch_q, sort)
    fetch_q = fetch_q.offset((page - 1) * size).limit(size)

    result = await db.execute(fetch_q)
    issues = list(result.scalars().all())

    enriched = await _build_enriched_responses(issues, db, current_user)
    return IssueListResponse(items=enriched, total=total, page=page, size=size)


@router.get("/export", summary="Export issues as CSV")
async def export_issues(
    project_id: int | None = Query(None),
    release_id: int | None = Query(None),
    status: IssueStatus | None = Query(None),
    statuses: str | None = Query(
        None, description="Comma-separated statuses, e.g. new,triaged,in_progress"
    ),
    severity: IssueSeverity | None = Query(None),
    assignee_id: int | None = Query(None),
    is_regression: bool | None = Query(None),
    is_release_blocker: bool | None = Query(None),
    unassigned: bool | None = Query(None),
    labels: list[str] | None = Query(None),
    sort: str = Query("newest"),
    search: str | None = Query(None),
    type: IssueType | None = Query(None),
    is_urgent: bool | None = Query(None),
    has_release: bool | None = Query(None),
    project_kind: ProjectKind | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Export all matching issues as a CSV file (no pagination)."""
    filter_kwargs = dict(
        project_id=project_id,
        release_id=release_id,
        status=status,
        statuses=_parse_statuses(statuses),
        severity=severity,
        assignee_id=assignee_id,
        is_regression=is_regression,
        is_release_blocker=is_release_blocker,
        unassigned=unassigned,
        labels=labels,
        search=search,
        type=type,
        is_urgent=is_urgent,
        has_release=has_release,
        project_kind=project_kind,
    )

    fetch_q = select(Issue).options(
        selectinload(Issue.assignee),
        selectinload(Issue.reporter),
        selectinload(Issue.release),
    )
    fetch_q = _apply_filters(fetch_q, **filter_kwargs)
    fetch_q = _apply_sort(fetch_q, sort)

    result = await db.execute(fetch_q)
    issues = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Key", "Issue #", "Issue ID", "Type", "Title", "Severity", "Priority", "Urgent",
        "Status", "Assignee", "Reporter", "Release", "Due Date", "Labels",
        "Release Blocker", "Regression", "Created At", "Updated At",
    ])
    for issue in issues:
        item_type = getattr(issue.type, "value", issue.type) or IssueType.bug.value
        writer.writerow([
            issue_key(item_type, issue.issue_number),
            issue.issue_number,
            str(issue.id),
            item_type,
            issue.title,
            issue.severity,
            issue.priority,
            "Yes" if issue.is_urgent else "No",
            issue.status,
            issue.assignee.name if issue.assignee else "",
            issue.reporter.name if issue.reporter else "",
            issue.release.version if issue.release else "",
            issue.due_date.isoformat() if issue.due_date else "",
            ", ".join(issue.labels or []),
            "Yes" if issue.is_release_blocker else "No",
            "Yes" if issue.is_regression else "No",
            issue.created_at.isoformat(),
            issue.updated_at.isoformat(),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="issues.csv"'},
    )


@router.get(
    "/by-number/{issue_number}", response_model=IssueResponse, summary="Get issue by number",
)
async def get_issue_by_number(
    issue_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Return a single issue by its global issue_number (e.g. the number in issue-10)."""
    result = await db.execute(
        select(Issue).options(
            selectinload(Issue.assignee),
            selectinload(Issue.reporter),
            selectinload(Issue.release),
            selectinload(Issue.project),
        ).where(Issue.issue_number == issue_number, Issue.deleted_at.is_(None))
        .limit(1)
    )
    issue = result.scalars().first()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    enriched = await _build_enriched_responses([issue], db, current_user)
    return enriched[0]


@router.get("/by-number/{issue_number}/adjacent", summary="Get adjacent issue numbers")
async def get_adjacent_issues(
    issue_number: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the previous and next non-deleted issue_numbers relative to the given one."""
    prev_result = await db.execute(
        select(Issue.issue_number)
        .where(Issue.issue_number < issue_number, Issue.deleted_at.is_(None))
        .order_by(Issue.issue_number.desc())
        .limit(1)
    )
    next_result = await db.execute(
        select(Issue.issue_number)
        .where(Issue.issue_number > issue_number, Issue.deleted_at.is_(None))
        .order_by(Issue.issue_number.asc())
        .limit(1)
    )
    return {
        "prev_number": prev_result.scalar_one_or_none(),
        "next_number": next_result.scalar_one_or_none(),
    }


@router.post(
    "",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="File a new issue",
)
async def create_issue(
    payload: IssueCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """File a new bug or task. Release is optional (hotfixes, tasks). Any authenticated user can file issues."""
    issue = await issue_service.create(db, payload, current_user)
    await db.commit()
    result = await db.execute(
        select(Issue)
        .where(Issue.id == issue.id)
        .options(
            selectinload(Issue.assignee),
            selectinload(Issue.reporter),
            selectinload(Issue.release),
            selectinload(Issue.project),
        )
    )
    issue = result.scalar_one()
    from app.tasks.search import embed_issue
    embed_issue.apply_async((issue.id,), countdown=0)
    enriched = await _build_enriched_responses([issue], db, current_user)
    return enriched[0]


@router.get("/trash", response_model=list[TrashIssueResponse], summary="List soft-deleted issues")
async def list_trash(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.cto, UserRole.admin)),
) -> list[TrashIssueResponse]:
    """Return all soft-deleted issues ordered by most recently deleted first."""
    result = await db.execute(
        select(Issue)
        .options(
            selectinload(Issue.release),
            selectinload(Issue.project),
            selectinload(Issue.reporter),
            selectinload(Issue.deleted_by),
        )
        .where(Issue.deleted_at.isnot(None))
        .order_by(Issue.deleted_at.desc())
    )
    issues = result.scalars().all()
    return [
        TrashIssueResponse(
            id=i.id,
            issue_number=i.issue_number,
            type=i.type,
            title=i.title,
            description=i.description,
            severity=i.severity,
            status=i.status,
            release_id=i.release_id,
            release_name=i.release.version if i.release else None,
            project_id=i.project_id,
            project_name=i.project.name if i.project else None,
            reporter_id=i.reporter_id,
            reporter_name=i.reporter.name if i.reporter else None,
            reporter_username=i.reporter.username if i.reporter else None,
            reporter_avatar_color=i.reporter.avatar_color if i.reporter else None,
            reporter_avatar_url=i.reporter.avatar_url if i.reporter else None,
            deleted_at=i.deleted_at,
            deleted_by_id=i.deleted_by_id,
            deleted_by_name=i.deleted_by.name if i.deleted_by else None,
            deleted_by_username=i.deleted_by.username if i.deleted_by else None,
            deleted_by_avatar_color=i.deleted_by.avatar_color if i.deleted_by else None,
            deleted_by_avatar_url=i.deleted_by.avatar_url if i.deleted_by else None,
        )
        for i in issues
    ]


@router.delete(
    "/trash/clear",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete all trashed issues",
)
async def clear_trash(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.cto, UserRole.admin)),
) -> None:
    """Hard-delete every soft-deleted issue (DB CASCADE removes all related rows)."""
    await db.execute(sa_delete(Issue).where(Issue.deleted_at.isnot(None)))
    await db.commit()


@router.get("/{issue_id}", response_model=IssueResponse, summary="Get issue detail")
async def get_issue(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Return a single issue by UUID."""
    result = await db.execute(
        select(Issue).options(
            selectinload(Issue.assignee),
            selectinload(Issue.reporter),
            selectinload(Issue.release),
            selectinload(Issue.project),
        ).where(Issue.id == issue_id, Issue.deleted_at.is_(None))
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
    enriched = await _build_enriched_responses([issue], db, current_user)
    return enriched[0]


@router.patch("/{issue_id}", response_model=IssueResponse, summary="Update issue fields")
async def update_issue(
    issue_id: int,
    payload: IssueUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Partially update editable fields of an issue; emits a timeline event per changed field."""
    issue = await issue_service.update(
        db=db,
        issue_id=issue_id,
        payload=payload.model_dump(exclude_unset=True),
        actor=current_user,
    )
    await db.commit()
    from app.tasks.search import embed_issue
    embed_issue.apply_async((issue.id,), countdown=10)
    result = await db.execute(
        select(Issue).options(
            selectinload(Issue.assignee),
            selectinload(Issue.reporter),
            selectinload(Issue.release),
            selectinload(Issue.project),
        ).where(Issue.id == issue_id)
    )
    issue = result.scalar_one()
    enriched = await _build_enriched_responses([issue], db, current_user)
    return enriched[0]


@router.delete(
    "/{issue_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete issue",
)
async def delete_issue(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Soft-delete an issue (CTO, admin, reporter, or triage lead of the issue's release)."""
    result = await db.execute(
        select(Issue)
        .options(selectinload(Issue.release), selectinload(Issue.project))
        .where(Issue.id == issue_id, Issue.deleted_at.is_(None))
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

    is_privileged = current_user.role in (UserRole.admin, UserRole.cto)
    is_reporter = issue.reporter_id == current_user.id
    is_project_triage_lead = (
        issue.project is not None
        and issue.project.triage_lead_id == current_user.id
    )
    if not (is_privileged or is_reporter or is_project_triage_lead):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this issue",
        )

    from datetime import datetime
    issue.deleted_at = datetime.now(tz=UTC)
    issue.deleted_by_id = current_user.id
    db.add(issue)
    await db.commit()


@router.post(
    "/{issue_id}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Restore a soft-deleted issue",
)
async def restore_issue(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.cto, UserRole.admin)),
) -> None:
    """Undelete a soft-deleted issue, making it visible again in all issue lists."""
    result = await db.execute(
        select(Issue).where(Issue.id == issue_id, Issue.deleted_at.isnot(None))
    )
    issue = result.scalar_one_or_none()
    if issue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found in trash",
        )
    issue.deleted_at = None
    issue.deleted_by_id = None
    db.add(issue)
    await db.commit()


@router.delete(
    "/{issue_id}/permanent",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Permanently delete a single trashed issue",
)
async def permanent_delete_issue(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.cto, UserRole.admin)),
) -> None:
    """Hard-delete a single soft-deleted issue; DB CASCADE removes all related rows."""
    result = await db.execute(
        select(Issue.id).where(Issue.id == issue_id, Issue.deleted_at.isnot(None))
    )
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found in trash",
        )
    await db.execute(sa_delete(Issue).where(Issue.id == issue_id))
    await db.commit()


@router.post("/{issue_id}/triage", response_model=IssueResponse, summary="Triage an issue")
async def triage_issue(
    issue_id: int,
    payload: TriageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Triage: assign the issue and confirm severity. Maps to new -> todo."""
    await issue_service.triage(
        db, issue_id, payload.assignee_id, payload.severity, current_user,
        labels=payload.labels, is_release_blocker=payload.is_release_blocker,
    )
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post(
    "/{issue_id}/needs-clarification",
    response_model=IssueResponse,
    summary="Request clarification from reporter",
)
async def needs_clarification(
    issue_id: int,
    payload: NeedsClarificationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Move the issue to Needs info and ask the reporter for more information."""
    await issue_service.needs_clarification(
        db, issue_id, current_user, message=payload.message
    )
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post("/{issue_id}/fix", response_model=IssueResponse, summary="Mark issue as fixed")
async def mark_fixed(
    issue_id: int,
    payload: FixRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Developer marks the issue as fixed (optionally linking the MR). Maps to -> in_review."""
    await issue_service.mark_fixed(db, issue_id, payload.mr_url, current_user)
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post("/{issue_id}/verify", response_model=IssueResponse, summary="Verify a fix")
async def verify_fix(
    issue_id: int,
    payload: VerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """QA verifies the developer's fix. Outcome: pass | fail | partial."""
    await issue_service.verify_fix(db, issue_id, payload.outcome, current_user)
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post("/{issue_id}/reopen", response_model=IssueResponse, summary="Reopen issue")
async def reopen_issue(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Reopen a Done bug. Maps to the regression action; 409 done_is_final otherwise."""
    await issue_service.reopen(db, issue_id, current_user)
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post(
    "/{issue_id}/duplicate",
    response_model=IssueResponse,
    summary="Link issue as duplicate",
)
async def link_duplicate(
    issue_id: int,
    payload: DuplicateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Mark this issue as a duplicate of another issue and cancel it."""
    await issue_service.link_duplicate(db, issue_id, payload.parent_id, current_user)
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post("/{issue_id}/transition", response_model=IssueResponse, summary="Change status")
async def transition_issue(
    issue_id: int,
    payload: TransitionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Move the issue to a new status. Used by board drags and status menus.

    409 with ``{detail, code, allowed}`` when Workflow refuses the move.
    """
    issue = await issue_service.get(db, issue_id)
    await issue_service.transition(
        db, issue, to=payload.to, actor=current_user,
        reason=payload.reason, comment=payload.comment, cancel_reason=payload.cancel_reason,
    )
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post("/{issue_id}/regression", response_model=IssueResponse, summary="Flag a regression")
async def flag_regression(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Flag a regression on a Done or In review bug (BR-24). Requires an unshipped release."""
    await issue_service.regress(db, issue_id, current_user)
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.get(
    "/{issue_id}/cycles",
    response_model=list[IssueCycleResponse],
    summary="List per-iteration cycles for an issue",
)
async def list_issue_cycles(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[IssueCycleResponse]:
    """Return all workflow cycles for an issue, ordered by cycle number."""
    result = await db.execute(
        select(IssueCycle)
        .where(IssueCycle.issue_id == issue_id)
        .order_by(IssueCycle.cycle_number.asc())
    )
    cycles = result.scalars().all()
    return [IssueCycleResponse.from_orm_with_flag(c) for c in cycles]


@router.get(
    "/{issue_id}/regressions",
    response_model=list[RegressionHistoryResponse],
    summary="List regression history for an issue",
)
async def list_regression_history(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RegressionHistoryResponse]:
    """Return all regression events recorded for an issue, ordered oldest-first."""
    result = await db.execute(
        select(RegressionHistory)
        .options(
            selectinload(RegressionHistory.release),
            selectinload(RegressionHistory.detected_by),
            selectinload(RegressionHistory.previous_fix_by),
        )
        .where(RegressionHistory.issue_id == issue_id)
        .order_by(RegressionHistory.detected_at.asc())
    )
    histories = result.scalars().all()

    responses = []
    for h in histories:
        responses.append(RegressionHistoryResponse(
            id=h.id,
            regression_number=h.regression_number,
            detected_at=h.detected_at,
            release_id=h.release_id,
            release_version=h.release.version if h.release else None,
            detected_by=UserSummary.model_validate(h.detected_by) if h.detected_by else None,
            previous_fix_by=(
                UserSummary.model_validate(h.previous_fix_by) if h.previous_fix_by else None
            ),
        ))
    return responses
