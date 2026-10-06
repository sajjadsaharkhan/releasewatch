"""Issue endpoints.

GET    /issues                              — list issues (filters + sort handled server-side)
GET    /issues/export                       — export issues as CSV
GET    /issues/trash                        — list soft-deleted issues (CTO/admin only)
DELETE /issues/trash/clear                  — permanently delete all trashed issues (CTO/admin only)
POST   /issues                             — file a new issue
POST   /issues/bulk-move                    — move backlog items to a release, all or nothing
GET    /issues/{id}                         — get issue detail
PATCH  /issues/{id}                         — update issue fields
DELETE /issues/{id}                         — delete issue (CTO, admin, reporter, or triage lead)
POST   /issues/{id}/restore                 — restore a soft-deleted issue (CTO/admin only)
DELETE /issues/{id}/permanent               — permanently delete one trashed issue (CTO/admin only)
POST   /issues/{id}/triage                  — apply a triage outcome (accept | needs_info | duplicate | reject)
POST   /issues/{id}/move                    — move an open item to another project, with its placement
POST   /issues/{id}/recurrences             — report a recurrence on an open or Cancelled bug
POST   /issues/{id}/fix                     — mark as fixed (-> in_review)
POST   /issues/{id}/verify                  — verify the fix (-> done; fail → 409 use_reject)
POST   /issues/{id}/reject                  — Reject To review / In review / Done work (09a)
POST   /issues/{id}/returns                 — alias of /reject for Done items (08a)
POST   /issues/{id}/reopen                  — alias of /reject for Done items (Phase 1)
POST   /issues/{id}/transition              — generic status change; used by board drags and menus
GET    /issues/by-number/{n}/adjacent       — prev/next non-deleted issue numbers

Every status change goes through ``IssueService.transition()``
(``app/workflow.py`` decides what's allowed) — see
docs/phase-2/02-unified-status-model.md.

Every route checks ``app/policy.py`` (who may act) via ``app/services/authz.py``,
and every read starts from ``visible_issues`` — an item the caller may not see
is a 404, never a 403 (docs/phase-2/04-roles-and-visibility.md).
"""

import csv
import io
from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import case, func, or_, select
from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth import get_current_user, require_role
from app.core.errors import DomainError
from app.db.models.issue import (
    PRIORITY_RANK, Issue, IssueStatus, IssueType, Priority, issue_key, issue_type_value,
)
from app.db.models.issue_cycle import IssueCycle
from app.db.models.label import Label
from app.db.models.project import Project
from app.db.models.release import Release, ReleaseKind
from app.db.models.search import DuplicateHint
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.policy import Action, Target, item_actions, transition
from app.search import duplicate_hints, jev_settings
from app.tasks import search_index
from app.schemas.issue import (
    SubscriberOut,
    BlockedAction,
    BlockedTransition,
    BulkMoveRequest,
    BulkMoveResponse,
    DuplicateHintsResponse,
    FixRequest,
    IssueCreate,
    IssueCycleResponse,
    IssueListResponse,
    IssueResponse,
    IssueUpdate,
    LabelDetail,
    MoveRequest,
    RecurrenceCreate,
    RejectRequest,
    TransitionRequest,
    TrashIssueResponse,
    TriageRequest,
    UserSummary,
    VerifyRequest,
)
from app.services.authz import (
    actor_of,
    authorize,
    authorize_issue,
    issue_target,
    load_visible_issue,
    project_target,
    visibility_clause,
)
from app.services.cycle_metrics import is_regression_expr, regression_counts
from app.services.issue_service import issue_service
from app.services.subscriber_service import set_subscription, subscription_state
from app.services.subscriber_service import subscribers as list_subscribers
from app.workflow import Workflow

router = APIRouter()

#: Highest priority first; unrated items last (FR-37).
_PRIORITY_ORDER = case(
    *((Issue.priority == p.value, rank) for p, rank in PRIORITY_RANK.items()),
    else_=len(PRIORITY_RANK) + 1,
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
    actor: User,
    project_id,
    release_id,
    status,
    statuses=None,
    priority,
    assignee_id,
    reporter_id=None,
    is_regression,
    is_release_blocker,
    unassigned,
    labels,
    search,
    type=None,
    container=None,
    is_tech_debt=None,
):
    query = query.where(Issue.deleted_at.is_(None), visibility_clause(actor))
    if project_id:
        query = query.where(Issue.project_id == project_id)
    if release_id:
        query = query.where(Issue.release_id == release_id)
    if status:
        query = query.where(Issue.status == status)
    if statuses:
        query = query.where(Issue.status.in_(statuses))
    if priority:
        query = query.where(Issue.priority == priority)
    if assignee_id:
        query = query.where(Issue.assignee_id == assignee_id)
    if reporter_id:
        query = query.where(Issue.reporter_id == reporter_id)
    if is_regression is not None:
        # Phase 1's flag, read from cycles (08a Part 2).
        flag = is_regression_expr()
        query = query.where(flag if is_regression else ~flag)
    if is_release_blocker is not None:
        query = query.where(Issue.is_release_blocker == is_release_blocker)
    if unassigned:
        query = query.where(Issue.assignee_id.is_(None))
    if labels:
        query = query.where(or_(*[Issue.labels.any(name) for name in labels]))
    if type:
        query = query.where(Issue.type == type)
    if container == "backlog":
        query = query.where(Issue.release_id.is_(None))
    elif container == "stream":
        query = query.where(
            Issue.release_id.in_(select(Release.id).where(Release.kind == ReleaseKind.stream.value))
        )
    elif container:
        query = query.where(Issue.release_id == int(container))
    if is_tech_debt is not None:
        query = query.where(Issue.is_tech_debt == is_tech_debt)
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


#: PATCH fields that need their own Policy action on top of ``edit_item``.
_FIELD_ACTIONS = {
    "assignee_id": Action.assign,
    "priority": Action.set_priority,
    "due_date": Action.set_due_date,
}


def _apply_sort(query, sort: str):
    if sort == "oldest":
        return query.order_by(Issue.created_at.asc(), Issue.issue_number.asc())
    elif sort == "priority":
        return query.order_by(_PRIORITY_ORDER, Issue.created_at.desc(), Issue.issue_number.desc())
    elif sort == "reported":
        # Most reported first (slice 07) — ties by priority, then newest.
        return query.order_by(
            Issue.recurrence_count.desc(), _PRIORITY_ORDER,
            Issue.created_at.desc(), Issue.issue_number.desc(),
        )
    elif sort == "updated":
        return query.order_by(Issue.updated_at.desc(), Issue.issue_number.desc())
    else:
        return query.order_by(Issue.created_at.desc(), Issue.issue_number.desc())


def _workflow_fields(issue: Issue, current_user: User) -> dict:
    """Compute allowed/blocked transitions (Workflow ∩ Policy) and actions (Policy) for one issue."""
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
    allowed_actions, blocked_actions = item_actions(
        actor_of(current_user), issue_target(issue, issue.project), targets.allowed,
    )
    allowed_set = set(allowed_actions)
    blocked_by_policy = {b["action"]: b for b in blocked_actions}
    blocked_transitions = [BlockedTransition(**b) for b in targets.blocked]
    for to in targets.allowed:
        b = blocked_by_policy.get(transition(to))
        if b is not None:
            blocked_transitions.append(BlockedTransition(to=to, code=b["code"], detail=b["detail"]))
    return {
        "allowed_transitions": [to for to in targets.allowed if transition(to) in allowed_set],
        "blocked_transitions": blocked_transitions,
        "allowed_actions": allowed_actions,
        "blocked_actions": [BlockedAction(**b) for b in blocked_actions],
    }


async def _reload_and_enrich(db: AsyncSession, issue_id: int, current_user: User) -> IssueResponse:
    """Re-fetch an issue with its relations after a service call and enrich it.

    Used by every action endpoint (``/triage``, ``/fix``, ``/transition``, …)
    so the response always carries ``allowed_transitions`` for the next click.
    """
    # populate_existing: the service already loaded this issue into the session,
    # so without it the relations would be the ones from before the action.
    result = await db.execute(
        select(Issue).options(
            selectinload(Issue.assignee),
            selectinload(Issue.reporter),
            selectinload(Issue.release),
            selectinload(Issue.project),
        ).where(Issue.id == issue_id).execution_options(populate_existing=True)
    )
    issue = result.scalar_one()
    enriched = await _build_enriched_responses([issue], db, current_user)
    return enriched[0]


def _cycle_fields(issue: Issue, cycle: IssueCycle | None) -> dict:
    """The cycle badge and, while Rejected, why (09a) — from the current cycle.
    Cycles are numbered 1..N with no gaps, so the count is the current number."""
    if cycle is None:
        return {
            "cycle_count": 0, "cycle_number": None,
            "reject_reason": None, "reject_comment_id": None,
        }
    rejected = getattr(issue.status, "value", issue.status) == IssueStatus.rejected.value
    return {
        "cycle_count": cycle.cycle_number,
        "cycle_number": cycle.cycle_number,
        "reject_reason": (
            getattr(cycle.start_reason, "value", cycle.start_reason) if rejected else None
        ),
        "reject_comment_id": cycle.start_comment_id if rejected else None,
    }


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

    # The current cycle of every placed item, by primary key (08a Part 2) —
    # the cycle badge and the reject reason read it.
    cycle_ids = [i.current_cycle_id for i in issues if i.current_cycle_id is not None]
    cycles: dict[int, IssueCycle] = {}
    if cycle_ids:
        rows = await db.execute(select(IssueCycle).where(IssueCycle.id.in_(cycle_ids)))
        cycles = {c.id: c for c in rows.scalars().all()}

    # Possible-duplicate markers on triage rows (slice 14) — zero while Jev is
    # off, and one grouped count query only while it is on. Counted only for
    # New items, the way GET /duplicate-hints shows them (FR-S15): a bug moved
    # to Needs info keeps its stored hints but shows no marker.
    duplicates: dict[int, tuple[int, float]] = {}  # issue id → (count, best confidence)
    if issues and await jev_settings.is_enabled(db):
        new_ids = [
            i.id for i in issues
            if getattr(i.status, "value", i.status) == IssueStatus.new.value
        ]
        if new_ids:
            rows = await db.execute(
                select(DuplicateHint.issue_id, func.count(), func.max(DuplicateHint.confidence))
                .where(DuplicateHint.issue_id.in_(new_ids))
                .group_by(DuplicateHint.issue_id)
            )
            duplicates = {issue_id: (count, top) for issue_id, count, top in rows.all()}

    subscriptions = await subscription_state(db, [i.id for i in issues], current_user.id)

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
            "container_kind": getattr(issue.release.kind, "value", issue.release.kind) if issue.release else None,
            "release_status": getattr(issue.release.status, "value", issue.release.status) if issue.release else None,
            **_cycle_fields(issue, cycles.get(issue.current_cycle_id)),
            "project_triage_lead_id": issue.project.triage_lead_id if issue.project else None,
            "project_name": issue.project.name if issue.project else None,
            "project_slug": issue.project.slug if issue.project else None,
            "project_color": issue.project.color if issue.project else None,
            **_workflow_fields(issue, current_user),
            "possible_duplicates_count": duplicates.get(issue.id, (0, None))[0],
            "possible_duplicates_top": duplicates.get(issue.id, (0, None))[1],
            "subscriber_count": subscriptions.get(issue.id, (0, False))[0],
            "is_subscribed": subscriptions.get(issue.id, (0, False))[1],
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
    priority: Priority | None = Query(None),
    assignee_id: int | None = Query(None),
    reporter_id: int | None = Query(None),
    is_regression: bool | None = Query(None),
    is_release_blocker: bool | None = Query(None),
    unassigned: bool | None = Query(None),
    labels: list[str] | None = Query(None),
    sort: str = Query("newest"),
    search: str | None = Query(None),
    type: IssueType | None = Query(None),
    container: str | None = Query(
        None, pattern=r"^(backlog|stream|\d+)$",
        description="backlog (no container), stream (any project's Stream), or a container id.",
    ),
    is_tech_debt: bool | None = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueListResponse:
    """Return a paginated, filterable, sortable list of issues."""
    filter_kwargs = dict(
        actor=current_user,
        project_id=project_id,
        release_id=release_id,
        status=status,
        statuses=_parse_statuses(statuses),
        priority=priority,
        assignee_id=assignee_id,
        reporter_id=reporter_id,
        is_regression=is_regression,
        is_release_blocker=is_release_blocker,
        unassigned=unassigned,
        labels=labels,
        search=search,
        type=type,
        container=container,
        is_tech_debt=is_tech_debt,
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
    priority: Priority | None = Query(None),
    assignee_id: int | None = Query(None),
    is_regression: bool | None = Query(None),
    is_release_blocker: bool | None = Query(None),
    unassigned: bool | None = Query(None),
    labels: list[str] | None = Query(None),
    sort: str = Query("newest"),
    search: str | None = Query(None),
    type: IssueType | None = Query(None),
    container: str | None = Query(None, pattern=r"^(backlog|stream|\d+)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Export all matching issues as a CSV file (no pagination)."""
    filter_kwargs = dict(
        actor=current_user,
        project_id=project_id,
        release_id=release_id,
        status=status,
        statuses=_parse_statuses(statuses),
        priority=priority,
        assignee_id=assignee_id,
        is_regression=is_regression,
        is_release_blocker=is_release_blocker,
        unassigned=unassigned,
        labels=labels,
        search=search,
        type=type,
        container=container,
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
    regressed = await regression_counts(db, (i.id for i in issues))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Key", "Issue #", "Issue ID", "Type", "Title", "Priority",
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
            getattr(issue.priority, "value", issue.priority) or "",
            issue.status,
            issue.assignee.name if issue.assignee else "",
            issue.reporter.name if issue.reporter else "",
            issue.release.version if issue.release else "",
            issue.due_date.isoformat() if issue.due_date else "",
            ", ".join(issue.labels or []),
            "Yes" if issue.is_release_blocker else "No",
            "Yes" if regressed.get(issue.id) else "No",
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
        ).where(
            Issue.issue_number == issue_number,
            Issue.deleted_at.is_(None),
            visibility_clause(current_user),
        )
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
        .where(
            Issue.issue_number < issue_number, Issue.deleted_at.is_(None),
            visibility_clause(current_user),
        )
        .order_by(Issue.issue_number.desc())
        .limit(1)
    )
    next_result = await db.execute(
        select(Issue.issue_number)
        .where(
            Issue.issue_number > issue_number, Issue.deleted_at.is_(None),
            visibility_clause(current_user),
        )
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
    """File a new bug or task. Release is optional (hotfixes, tasks). Tech roles only (§7.3)."""
    authorize(current_user, Action.create_item)
    if payload.assignee_id is not None:
        authorize(current_user, Action.assign)
    if payload.is_tech_debt:
        # 409 tech_debt_task_only on a bug (BR-36, AC-31).
        authorize(current_user, Action.flag_tech_debt, Target(item_type=payload.type.value))
    if payload.is_release_blocker:
        project = await db.get(Project, payload.project_id)
        if project is not None:
            authorize(current_user, Action.flag_release_blocker, project_target(project))
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
    enriched = await _build_enriched_responses([issue], db, current_user)
    return enriched[0]


@router.post("/bulk-move", response_model=BulkMoveResponse, summary="Move items to the Stream or a release")
async def bulk_move(
    payload: BulkMoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BulkMoveResponse:
    """Move several items to one container — the Stream or an open Release — in
    one action (FR-25, slice 08; 08a).

    All or nothing: if any item can't move, nothing moves and the 409
    ``bulk_move_failed`` lists each failing id under ``errors`` (a Done item
    fails the request with ``done_item_immobile``, BR-54). Guarded by
    ``manage_backlog`` on the release's project.
    """
    from app.services.backlog_service import backlog_service, get_release_or_404

    from app.services import container_service as containers

    release = await get_release_or_404(db, payload.release_id)
    project = await db.get(Project, release.project_id)
    authorize(current_user, Action.manage_backlog, project_target(project))
    await containers.resolve(db, release.project_id, release.id)  # release_closed

    ids = list(dict.fromkeys(payload.issue_ids))
    rows = (await db.execute(
        select(Issue).where(
            Issue.id.in_(ids), Issue.deleted_at.is_(None), visibility_clause(current_user),
        ).with_for_update()
    )).scalars().all()
    found = {i.id: i for i in rows}
    moved = await backlog_service.bulk_move(
        db, {i: found.get(i) for i in ids}, release, current_user,
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
    return BulkMoveResponse(moved_ids=moved, items=items)


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
            priority=i.priority,
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
    """Return a single issue by id — 404 when the caller may not see it."""
    issue = await load_visible_issue(
        db, issue_id, current_user,
        selectinload(Issue.assignee),
        selectinload(Issue.reporter),
        selectinload(Issue.release),
        selectinload(Issue.project),
    )
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
    data = payload.model_dump(exclude_unset=True)
    issue = await authorize_issue(db, issue_id, current_user, Action.edit_item)
    if data.get("project_id") not in (None, issue.project_id):
        raise DomainError(
            status.HTTP_409_CONFLICT,
            "Use Move to change an item's project — it also picks the placement there.",
            "use_move",
        )
    data.pop("project_id", None)
    target = issue_target(issue, issue.project)
    for field, action in _FIELD_ACTIONS.items():
        if field in data:
            authorize(current_user, action, target)
    if "is_release_blocker" in data and data["is_release_blocker"] != issue.is_release_blocker:
        authorize(current_user, Action.flag_release_blocker, target)
    if data.get("is_tech_debt") is not None and data["is_tech_debt"] != issue.is_tech_debt:
        authorize(current_user, Action.flag_tech_debt, target)
    if data.get("status") is not None:
        authorize(current_user, transition(data["status"]), target)
    issue = await issue_service.update(
        db=db,
        issue_id=issue_id,
        payload=data,
        actor=current_user,
    )
    await db.commit()
    # populate_existing: the session keeps objects across commit, so without it the
    # view-only backlog_category would still be the one loaded before the change.
    result = await db.execute(
        select(Issue).options(
            selectinload(Issue.assignee),
            selectinload(Issue.reporter),
            selectinload(Issue.release),
            selectinload(Issue.project),
        ).where(Issue.id == issue_id).execution_options(populate_existing=True)
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
    issue = await load_visible_issue(
        db, issue_id, current_user, selectinload(Issue.release), selectinload(Issue.project),
    )

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

    await issue_service.set_deleted(db, issue, current_user, True)
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
    await issue_service.set_deleted(db, issue, current_user, False)
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


@router.post("/{issue_id}/triage", response_model=IssueResponse, summary="Apply a triage outcome")
async def triage_issue(
    issue_id: int,
    payload: TriageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Accept, Needs info, Duplicate, or Reject a New or Needs info bug (slice 06).

    409 ``not_in_triage`` outside New/Needs info; the Duplicate outcome adds
    ``duplicate_of_self``, ``duplicate_cross_project``
    and ``duplicate_of_duplicate`` (with ``suggested_id``).
    """
    from app.services.triage_service import triage_service

    issue = await authorize_issue(db, issue_id, current_user, Action.triage)
    await triage_service.apply(db, issue, payload, current_user)
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post("/{issue_id}/move", response_model=IssueResponse, summary="Move to another project")
async def move_issue(
    issue_id: int,
    payload: MoveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Move an open item to another project and place it there (FR-20): the
    destination's Stream, an open Release, or its backlog (Move… dialog)."""
    from app.services.triage_service import triage_service

    issue = await authorize_issue(db, issue_id, current_user, Action.edit_item)
    await triage_service.move_project(
        db, issue, payload.project_id, current_user,
        release_id=payload.release_id, backlog_category_id=payload.backlog_category_id,
    )
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post(
    "/{issue_id}/recurrences",
    response_model=IssueResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Report a recurrence",
)
async def report_recurrence(
    issue_id: int,
    payload: RecurrenceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Record one more occurrence of an open or Cancelled bug (slice 07, FR-13–16).

    Any role, on a bug they can see. 422 on an empty comment; 409
    ``recurrence_bug_only`` on a task and ``recurrence_on_done`` on a Done bug.
    """
    from app.services.recurrence_service import recurrence_service

    issue = await authorize_issue(db, issue_id, current_user, Action.report_recurrence)
    await recurrence_service.report(db, issue, payload, current_user)
    await db.commit()

    return await _reload_and_enrich(db, issue_id, current_user)


@router.put("/{issue_id}/subscription", response_model=IssueResponse, summary="Subscribe to an item")
@router.delete("/{issue_id}/subscription", response_model=IssueResponse, summary="Unsubscribe from an item")
async def change_subscription(
    issue_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Track (PUT) or stop tracking (DELETE) an item the caller can see — any
    role, Support included (it still hears only its three events). Idempotent;
    each real change lands on the timeline for every member."""
    await load_visible_issue(db, issue_id, current_user)
    await set_subscription(db, issue_id, current_user.id, subscribed=request.method == "PUT")
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.get(
    "/{issue_id}/subscribers",
    response_model=list[SubscriberOut],
    summary="Who is subscribed to an item",
)
async def get_subscribers(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SubscriberOut]:
    """The subscriber list behind the Subscribe button's hover card — any user
    who can see the item (404 otherwise)."""
    await load_visible_issue(db, issue_id, current_user)
    return [
        SubscriberOut(
            user=UserSummary.model_validate(user),
            reason=getattr(sub.reason, "value", sub.reason),
            subscribed_at=sub.created_at,
        )
        for user, sub in await list_subscribers(db, issue_id)
    ]


@router.get(
    "/{issue_id}/duplicate-hints",
    response_model=DuplicateHintsResponse,
    summary="Possible duplicates of a New item",
)
async def get_duplicate_hints(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DuplicateHintsResponse:
    """Stored triage hints for a New bug (slice 14, FR-S12–S15). Tech only —
    Support gets 403 on items they can see and 404 on items they can't (FR-S13).
    ``[]`` unless the item is New and Jev is enabled: hidden, never deleted
    (BR-S03). Each hint says what merging will do, computed the way the merge
    itself does (BR-49)."""
    issue = await authorize_issue(db, issue_id, current_user, Action.view_duplicate_hints)
    if not duplicate_hints.is_hintable(issue) or not await jev_settings.is_enabled(db):
        return DuplicateHintsResponse(hints=[])
    hints = await duplicate_hints.hydrate(db, issue_id)
    # Never judged (filed before Jev was on, or the job failed): ask for a run
    # now, not after an edit's debounce, and tell the client to look again.
    computing = not hints and issue.duplicate_hints_computed_at is None
    if computing:
        search_index.request_hints_on_open(issue.id)
    return DuplicateHintsResponse(hints=hints, computing=computing)


@router.post(
    "/{issue_id}/duplicate-hints/{candidate_id}/dismiss",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dismiss a possible duplicate for good",
)
async def dismiss_duplicate_hint(
    issue_id: int,
    candidate_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """"Not a duplicate": the pair is never suggested again, whatever future
    recomputations find (BR-S12, AC-S12). Tech only."""
    await authorize_issue(db, issue_id, current_user, Action.view_duplicate_hints)
    await duplicate_hints.dismiss(db, issue_id, candidate_id, current_user.id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{issue_id}/fix", response_model=IssueResponse, summary="Mark issue as fixed")
async def mark_fixed(
    issue_id: int,
    payload: FixRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Developer marks the issue as fixed (optionally linking the MR). Maps to -> in_review."""
    await authorize_issue(db, issue_id, current_user, transition(IssueStatus.in_review))
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
    to = {"pass": IssueStatus.done, "fail": IssueStatus.in_progress}.get(
        payload.outcome, IssueStatus.in_review,
    )
    await authorize_issue(db, issue_id, current_user, transition(to))
    await issue_service.verify_fix(db, issue_id, payload.outcome, current_user, payload.note)
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post("/{issue_id}/reject", response_model=IssueResponse, summary="Reject work")
async def reject_issue(
    issue_id: int,
    payload: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Reject (09a): send To review, In review or Done work back with a comment.

    The item lands in Rejected and starts its next cycle; the server decides
    where the problem was caught (``review`` / ``release_qa`` / ``production``).
    409 ``not_rejectable`` from any other status; 422 without a comment.
    """
    issue = await authorize_issue(db, issue_id, current_user, Action.reject)
    await issue_service.reject(db, issue, payload.comment, current_user)
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


async def _authorize_reject_done(db: AsyncSession, issue_id: int, user: User) -> Issue:
    """The aliases keep their Phase 1 / 08a precondition: Done items only (409
    ``not_done``), checked before Policy's own status rule."""
    issue = await authorize_issue(db, issue_id, user, Action.view_item)
    issue_service.ensure_done(issue)
    authorize(user, Action.reject, issue_target(issue, issue.project))
    return issue


@router.post("/{issue_id}/returns", response_model=IssueResponse, summary="Reject Done work")
async def return_issue(
    issue_id: int,
    payload: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """08a's return — an alias of ``/reject`` for Done items."""
    issue = await _authorize_reject_done(db, issue_id, current_user)
    await issue_service.reject(db, issue, payload.comment, current_user)
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.post("/{issue_id}/reopen", response_model=IssueResponse, summary="Reopen issue")
async def reopen_issue(
    issue_id: int,
    payload: RejectRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueResponse:
    """Phase 1's reopen — an alias of ``/reject`` for Done items (09a)."""
    issue = await _authorize_reject_done(db, issue_id, current_user)
    await issue_service.reject(
        db, issue, payload.comment if payload is not None else None, current_user,
    )
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

    409 with ``{detail, code, allowed}`` when Workflow refuses the move —
    ``use_reject`` for Rejected, which only ``/reject`` enters (09a).
    """
    issue = await authorize_issue(db, issue_id, current_user, transition(payload.to))
    await issue_service.transition(
        db, issue, to=payload.to, actor=current_user,
        reason=payload.reason, comment=payload.comment, cancel_reason=payload.cancel_reason,
    )
    await db.commit()
    return await _reload_and_enrich(db, issue_id, current_user)


@router.get(
    "/{issue_id}/cycles",
    response_model=list[IssueCycleResponse],
    summary="List the item's cycles",
)
async def list_issue_cycles(
    issue_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[IssueCycleResponse]:
    """The item's cycles in its current placement, oldest first (FR-66): when
    each started and why, who delivered it, when it was verified."""
    await load_visible_issue(db, issue_id, current_user)
    result = await db.execute(
        select(IssueCycle)
        .options(
            selectinload(IssueCycle.release),
            selectinload(IssueCycle.start_by),
            selectinload(IssueCycle.delivered_by),
        )
        .where(IssueCycle.issue_id == issue_id)
        .order_by(IssueCycle.cycle_number.asc())
    )
    return [
        IssueCycleResponse(
            id=c.id,
            issue_id=c.issue_id,
            cycle_number=c.cycle_number,
            release_id=c.release_id,
            release_version=c.release.version if c.release else None,
            container_kind=getattr(c.release.kind, "value", c.release.kind) if c.release else None,
            start_reason=getattr(c.start_reason, "value", c.start_reason),
            start_comment_id=c.start_comment_id,
            start_merged_issue_id=c.start_merged_issue_id,
            start_by=UserSummary.model_validate(c.start_by) if c.start_by else None,
            assignee_id=c.assignee_id,
            delivered_by=UserSummary.model_validate(c.delivered_by) if c.delivered_by else None,
            started_at=c.started_at,
            picked_up_at=c.picked_up_at,
            submitted_at=c.submitted_at,
            verified_at=c.verified_at,
            closed_at=c.closed_at,
        )
        for c in result.scalars().all()
    ]
