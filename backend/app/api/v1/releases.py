"""Releases API router — thin routes over ``ReleaseService`` (slice 09).

GET    /releases                          — releases across projects (never the Stream)
POST   /releases                          — create (Phase 1 shape; ``project_id`` in the body)
GET    /releases/{id}                     — one container (a Release or the Stream)
PATCH  /releases/{id}                     — edit fields; a ``status`` goes through the lifecycle
POST   /releases/{id}/status              — manual lifecycle move (FR-50)
POST   /releases/{id}/go-nogo             — record go or no-go (FR-52)
GET    /releases/{id}/ship-preview        — the ship notice (FR-53)
POST   /releases/{id}/ship                — ship (FR-53)
POST   /releases/{id}/cancel              — cancel (BR-55)
GET    /releases/{id}/items               — the Items tab
GET    /releases/{id}/activity            — the Activity tab (FR-51)
GET    /releases/{id}/board               — one group per board status; Done bounded by ``done_from``/``done_to``
GET    /releases/{id}/analytics           — cycle analytics (Phase 1 report)
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.clock import get_now
from app.db.models.issue import FIXED_STATUSES, Issue, IssueStatus
from app.db.models.project import Project
from app.db.models.release import GoNogoStatus, Release, ReleaseKind
from app.db.models.user import User
from app.db.session import get_db
from app.policy import Action
from app.schemas.issue import UserSummary
from app.schemas.release import (
    AnalyticsCycleRow,
    BoardColumn,
    GoNogoRequest,
    ReleaseActivityResponse,
    ReleaseAnalyticsResponse,
    ReleaseBoardResponse,
    ReleaseCreate,
    ReleaseEventResponse,
    ReleaseItemsResponse,
    ReleaseListResponse,
    ReleaseResponse,
    ReleaseStatusRequest,
    ReleaseUpdate,
    ShipPreviewResponse,
    ShipRequest,
)
from app.services.authz import authorize, project_target, require_action
from app.services.container_service import stream_immutable
from app.services.cycle_metrics import is_regression_expr
from app.services.release_service import is_overdue, progress, release_service

#: Cycle reasons Phase 1 counted as regressions (08a Part 2).
PHASE1_REASONS = ("review", "release_qa")

router = APIRouter()


async def _get_release_or_404(db: AsyncSession, release_id: int) -> Release:
    """Get a non-deleted container by ID or raise 404."""
    result = await db.execute(
        select(Release).where(Release.id == release_id, Release.deleted_at.is_(None))
    )
    release = result.scalar_one_or_none()
    if release is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Release not found"
        )
    return release


def refuse_stream(release: Release) -> None:
    """FR-46 — no edit, status change, archive, go/no-go, or delete on the Stream."""
    if release.is_stream:
        raise stream_immutable()


async def _authorize(db: AsyncSession, user: User, action: Action, project_id: int) -> None:
    """``action`` on the release's project (the triage-lead rules need it)."""
    authorize(user, action, project_target(await db.get(Project, project_id)))


async def _add_release_metrics(db: AsyncSession, release: Release) -> dict:
    """Phase 1 counters (open, blockers, total, fixed) plus the slice-09 counts."""
    counts = await release_service.counts(db, release.id)
    blockers = (await db.execute(
        select(func.count())
        .where(Issue.release_id == release.id, Issue.deleted_at.is_(None))
        .where(Issue.is_release_blocker == True)  # noqa: E712
        .where(Issue.status.notin_([IssueStatus.done, IssueStatus.cancelled]))
    )).scalar() or 0
    return {
        "open_issues": sum(counts.values()) - counts["done"] - counts["cancelled"],
        "blocker_count": blockers,
        "total_issues": sum(counts.values()),
        # "Fixed": delivered — to review, in review or done (09a).
        "fixed_issues": sum(counts[s.value] for s in FIXED_STATUSES),
        "counts": counts,
        "progress": None if release.is_stream else progress(counts),
    }


async def _release_to_response(
    db: AsyncSession, release: Release, user: User | None = None, now: datetime | None = None,
) -> ReleaseResponse:
    """A Release (or the Stream) with its metrics and, given ``user``, what they may do."""
    metrics = await _add_release_metrics(db, release)
    project = await db.get(Project, release.project_id)
    transitions, actions = (
        await release_service.permissions(db, release, user) if user is not None else ([], [])
    )
    data = {
        "id": release.id,
        "project_id": release.project_id,
        "kind": release.kind,
        "version": release.version,
        "description": release.description,
        "status": release.status,
        "target_date": release.target_date,
        "code_freeze_date": release.code_freeze_date,
        "released_at": release.released_at,
        "staging_url": release.staging_url,
        "go_nogo_status": release.go_nogo_status,
        "go_nogo_note": release.go_nogo_note,
        "go_nogo_by_id": release.go_nogo_by_id,
        "go_nogo_at": release.go_nogo_at,
        "created_by_id": release.created_by_id,
        "created_at": release.created_at,
        "updated_at": release.updated_at,
        "project_name": project.name if project else None,
        "project_slug": project.slug if project else None,
        "is_overdue": is_overdue(release, now or datetime.now(tz=UTC)),
        "allowed_transitions": transitions,
        "allowed_actions": actions,
        **metrics,
    }
    return ReleaseResponse(**data)


async def _respond(db: AsyncSession, release: Release, user: User, now: datetime) -> ReleaseResponse:
    await db.commit()
    await db.refresh(release)
    return await _release_to_response(db, release, user, now)


@router.get("", response_model=ReleaseListResponse, summary="List all releases")
async def list_releases(
    project_id: int | None = Query(None, description="Filter by project ID"),
    status: str | None = Query(None, description="Filter by status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.view_releases)),
    now: datetime = Depends(get_now),
) -> ReleaseListResponse:
    """Return all releases across all projects, most recent first. Never the
    Stream — release lists hold releases only (08a)."""
    query = (
        select(Release)
        .where(Release.deleted_at.is_(None), Release.kind == ReleaseKind.release.value)
        .order_by(Release.created_at.desc())
    )
    if project_id:
        query = query.where(Release.project_id == project_id)
    if status:
        query = query.where(Release.status == status)
    releases = (await db.execute(query)).scalars().all()
    responses = [await _release_to_response(db, r, current_user, now) for r in releases]
    return ReleaseListResponse(releases=responses, total=len(responses))


@router.post(
    "", response_model=ReleaseResponse, status_code=status.HTTP_201_CREATED,
    summary="Create a release",
)
async def create_release(
    payload: ReleaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    """Create a new release (it starts in Planning)."""
    project = await db.get(Project, payload.project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with ID {payload.project_id} not found",
        )
    authorize(current_user, Action.manage_releases, project_target(project))
    release = await release_service.create(db, project, payload.model_dump(), current_user)
    return await _respond(db, release, current_user, now)


@router.get("/{release_id}", response_model=ReleaseResponse, summary="Get a release")
async def get_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    authorize(current_user, Action.view_releases)
    release = await _get_release_or_404(db, release_id)
    return await _release_to_response(db, release, current_user, now)


@router.patch("/{release_id}", response_model=ReleaseResponse, summary="Update release metadata")
async def update_release(
    release_id: int,
    payload: ReleaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    """Edit fields (FR-49). A ``status`` goes through the lifecycle, so Released
    is refused here (``use_ship``)."""
    release = await _get_release_or_404(db, release_id)
    await _authorize(db, current_user, Action.manage_releases, release.project_id)
    await release_service.edit(db, release, payload.model_dump(exclude_unset=True), current_user)
    return await _respond(db, release, current_user, now)


@router.post("/{release_id}/status", response_model=ReleaseResponse, summary="Change lifecycle status")
async def change_release_status(
    release_id: int,
    payload: ReleaseStatusRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    release = await _get_release_or_404(db, release_id)
    refuse_stream(release)
    await _authorize(db, current_user, Action.manage_releases, release.project_id)
    await release_service.change_status(db, release, payload.to.value, current_user, now=now)
    return await _respond(db, release, current_user, now)


@router.post("/{release_id}/cancel", response_model=ReleaseResponse, summary="Cancel a release")
async def cancel_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    """BR-55: refused with a Done item; open items move to the backlog."""
    release = await _get_release_or_404(db, release_id)
    refuse_stream(release)
    await _authorize(db, current_user, Action.manage_releases, release.project_id)
    await release_service.cancel(db, release, current_user, now=now)
    return await _respond(db, release, current_user, now)


@router.post("/{release_id}/go-nogo", response_model=ReleaseResponse, summary="Record go or no-go")
async def go_nogo(
    release_id: int,
    payload: GoNogoRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    """CTO or Admin records go (``approved``) or no-go (``blocked``) with a note (FR-52)."""
    release = await _get_release_or_404(db, release_id)
    refuse_stream(release)
    await _authorize(db, current_user, Action.go_nogo, release.project_id)
    await release_service.go_nogo(
        db, release, payload.decision.value, payload.note, current_user, now=now,
    )
    return await _respond(db, release, current_user, now)


@router.get(
    "/{release_id}/ship-preview", response_model=ShipPreviewResponse, summary="The ship notice",
)
async def ship_preview(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ShipPreviewResponse:
    release = await _get_release_or_404(db, release_id)
    refuse_stream(release)
    await _authorize(db, current_user, Action.ship_release, release.project_id)
    return ShipPreviewResponse(**await release_service.ship_preview(db, release))


@router.post("/{release_id}/ship", response_model=ReleaseResponse, summary="Ship a release")
async def ship_release(
    release_id: int,
    payload: ShipRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    """FR-53: Released now; every item that isn't Done moves to the backlog."""
    release = await _get_release_or_404(db, release_id)
    refuse_stream(release)
    await _authorize(db, current_user, Action.ship_release, release.project_id)
    await release_service.ship(db, release, current_user, now=now)
    return await _respond(db, release, current_user, now)


# ── Items, board, activity ────────────────────────────────────────────────────


@router.get("/{release_id}/items", response_model=ReleaseItemsResponse, summary="The Items tab")
async def release_items(
    release_id: int,
    done_from: datetime | None = Query(None, description="Done items: completed at or after"),
    done_to: datetime | None = Query(None, description="Done items: completed at or before"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseItemsResponse:
    """Every item; Done ones bounded like the board's Done column (the Stream
    defaults to the last 7 days, a Release is unbounded)."""
    from app.api.v1.issues import _build_enriched_responses

    authorize(current_user, Action.view_releases)
    release = await _get_release_or_404(db, release_id)
    rows, done_from, done_to = await release_service.items(
        db, release, current_user, now=now, done_from=done_from, done_to=done_to,
    )
    items = await _build_enriched_responses(rows, db, current_user)
    return ReleaseItemsResponse(items=items, total=len(items), done_from=done_from, done_to=done_to)


@router.get("/{release_id}/board", response_model=ReleaseBoardResponse, summary="The board")
async def release_board(
    release_id: int,
    done_from: datetime | None = Query(None, description="Done column: completed at or after"),
    done_to: datetime | None = Query(None, description="Done column: completed at or before"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseBoardResponse:
    """One group per board status (09a adds Rejected and To review). Only Done is bounded: by default the last 7 days on the
    Stream (FR-47, AC-63) and unbounded on a Release."""
    from app.api.v1.issues import _build_enriched_responses

    authorize(current_user, Action.view_releases)
    release = await _get_release_or_404(db, release_id)
    columns, done_from, done_to = await release_service.board(
        db, release, current_user, now=now, done_from=done_from, done_to=done_to,
    )
    return ReleaseBoardResponse(
        columns=[
            BoardColumn(status=col, items=await _build_enriched_responses(items, db, current_user))
            for col, items in columns
        ],
        done_from=done_from,
        done_to=done_to,
    )


@router.get(
    "/{release_id}/activity", response_model=ReleaseActivityResponse, summary="The Activity tab",
)
async def release_activity(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReleaseActivityResponse:
    """Created, lifecycle, dates, items added or removed, go/no-go, ship, edits — oldest first."""
    authorize(current_user, Action.view_releases)
    release = await _get_release_or_404(db, release_id)
    events = await release_service.activity(db, release.id)
    return ReleaseActivityResponse(events=[
        ReleaseEventResponse(
            id=e.id,
            event_type=getattr(e.event_type, "value", e.event_type),
            actor=UserSummary.model_validate(e.actor) if e.actor else None,
            meta=e.meta,
            created_at=e.created_at,
        )
        for e in events
    ])


@router.get(
    "/{release_id}/analytics",
    response_model=ReleaseAnalyticsResponse,
    summary="Cycle-accurate analytics for a release",
)
async def get_release_analytics(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReleaseAnalyticsResponse:
    """Return all issue cycles for a release so the frontend can compute
    accurate per-iteration MTTF / MTTV / MTTT and regression rate.

    Each row carries the parent issue's priority and labels so the caller
    can group/filter without extra requests.
    """
    from app.db.models.issue_cycle import IssueCycle

    authorize(current_user, Action.view_releases)
    release = await _get_release_or_404(db, release_id)

    # Fetch all cycles joined to their parent issue
    rows = await db.execute(
        select(IssueCycle, Issue)
        .join(Issue, IssueCycle.issue_id == Issue.id)
        .where(IssueCycle.release_id == release.id)
        .order_by(IssueCycle.issue_id, IssueCycle.cycle_number)
    )
    pairs = rows.all()

    # Aggregate totals
    issue_ids = {issue.id for _, issue in pairs}
    total_issues = len(issue_ids)

    verified_q = await db.execute(
        select(func.count(Issue.id))
        .where(Issue.release_id == release.id)
        .where(Issue.verified_at.isnot(None))
    )
    verified_issues = verified_q.scalar_one()

    regression_q = await db.execute(
        select(func.count(Issue.id))
        .where(Issue.release_id == release.id)
        .where(is_regression_expr())
    )
    regression_count = regression_q.scalar_one()

    def hours(end, start):
        return round((end - start).total_seconds() / 3600, 2) if end and start else None

    cycles = []
    for cycle, issue in pairs:
        # Phase 1 measured the first fix from triage; later passes from their start.
        first = cycle.cycle_number == 1
        triaged_at = issue.triaged_at if first else None
        fix_from = max(cycle.started_at, triaged_at) if triaged_at else cycle.started_at
        cycles.append(AnalyticsCycleRow(
            issue_id=cycle.issue_id,
            issue_priority=getattr(issue.priority, "value", issue.priority),
            issue_labels=issue.labels or [],
            cycle_number=cycle.cycle_number,
            start_reason=getattr(cycle.start_reason, "value", cycle.start_reason),
            is_regression_cycle=(
                getattr(issue.type, "value", issue.type) == "bug"
                and getattr(cycle.start_reason, "value", cycle.start_reason) in PHASE1_REASONS
                and not release.is_stream
            ),
            triaged_at=triaged_at,
            fixed_at=cycle.submitted_at,
            verified_at=cycle.verified_at,
            time_to_triage_h=hours(triaged_at, cycle.started_at) if first else None,
            time_to_fix_h=hours(cycle.submitted_at, fix_from),
            time_to_verify_h=hours(cycle.verified_at, cycle.submitted_at),
        ))

    return ReleaseAnalyticsResponse(
        total_issues=total_issues,
        verified_issues=verified_issues,
        regression_count=regression_count,
        cycles=cycles,
    )


@router.post("/{release_id}/approve", response_model=ReleaseResponse, summary="Approve a release")
async def approve_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    """Phase 1 alias of ``POST /go-nogo`` with ``approved``."""
    release = await _get_release_or_404(db, release_id)
    refuse_stream(release)
    await _authorize(db, current_user, Action.go_nogo, release.project_id)
    await release_service.go_nogo(
        db, release, GoNogoStatus.approved.value, None, current_user, now=now,
    )
    return await _respond(db, release, current_user, now)


@router.post("/{release_id}/block", response_model=ReleaseResponse, summary="Block a release")
async def block_release(
    release_id: int,
    payload: GoNogoRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    """Phase 1 alias of ``POST /go-nogo`` with ``blocked``. A blocked release is
    one in QA with a no-go (08a), not a status."""
    release = await _get_release_or_404(db, release_id)
    refuse_stream(release)
    await _authorize(db, current_user, Action.go_nogo, release.project_id)
    await release_service.go_nogo(
        db, release, GoNogoStatus.blocked.value, payload.note, current_user, now=now,
    )
    return await _respond(db, release, current_user, now)


@router.delete("/{release_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a release")
async def delete_release(
    release_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Soft-delete a release (``manage_releases`` on its project); never a Released one."""
    release = await _get_release_or_404(db, release_id)
    await _authorize(db, current_user, Action.manage_releases, release.project_id)
    await release_service.delete(db, release)
    await db.commit()
