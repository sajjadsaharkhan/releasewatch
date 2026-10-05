"""Project and nested release endpoints.

GET    /projects                              — list projects
POST   /projects                              — create project
GET    /projects/{slug}                       — get project detail
PATCH  /projects/{slug}                       — update project
DELETE /projects/{slug}                       — archive project
GET    /projects/{ref}/releases               — list releases for project (slug or id)
POST   /projects/{ref}/releases               — create release (starts in Planning)
GET    /projects/{ref}/stream                 — the project's Stream (slice 09)
GET    /projects/{ref}/releases/{version}     — get release detail

Release edits, lifecycle, go/no-go and ship live on ``/releases/{id}`` (slice 09).
"""

from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.models.project import Project
from app.db.models.release import Release, ReleaseKind
from app.core.clock import get_now
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.project import ProjectArchiveRequest, ProjectCreate, ProjectResponse, ProjectUpdate
from app.schemas.release import ProjectReleaseCreate, ReleaseResponse
from app.policy import Action
from app.services.authz import authorize, project_target, require_action
from app.services.container_service import stream_of
from app.services.project_service import project_needs_triage_lead, validate_triage_lead

from app.services.support_service import support_service

router = APIRouter()

async def _backlog_category_count(db: AsyncSession, project_id: int) -> int:
    from sqlalchemy import func

    from app.db.models.backlog_category import BacklogCategory

    return (await db.execute(
        select(func.count(BacklogCategory.id)).where(BacklogCategory.project_id == project_id)
    )).scalar_one()


async def _project_to_response(db: AsyncSession, project: Project) -> ProjectResponse:
    """Build a ProjectResponse, resolving triage_lead_name and needs_triage_lead from the DB."""
    triage_lead_name: str | None = None
    if project.triage_lead_id:
        result = await db.execute(select(User).where(User.id == project.triage_lead_id))
        tl = result.scalar_one_or_none()
        if tl:
            triage_lead_name = tl.name or tl.username
    total, active = await support_service.template_counts(db, project.id)
    data = ProjectResponse.model_validate(project).model_dump(
        exclude={
            "triage_lead_name", "needs_triage_lead",
            "support_template_count", "active_support_template_count", "backlog_category_count",
            "stream_id",
        }
    )
    return ProjectResponse(
        **data,
        triage_lead_name=triage_lead_name,
        needs_triage_lead=await project_needs_triage_lead(db, project),
        support_template_count=total,
        active_support_template_count=active,
        backlog_category_count=await _backlog_category_count(db, project.id),
        stream_id=(await stream_of(db, project.id)).id,
    )


async def _apply_project_update(db: AsyncSession, project: Project, update_data: dict) -> None:
    if "triage_lead_id" in update_data:
        await validate_triage_lead(db, update_data["triage_lead_id"])
    for field, value in update_data.items():
        setattr(project, field, value)


# ── Projects ──────────────────────────────────────────────────────────────────

@router.get("", response_model=List[ProjectResponse], summary="List all projects")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ProjectResponse]:
    """Return all projects (active and archived) visible to the authenticated user."""
    result = await db.execute(
        select(Project).order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [await _project_to_response(db, p) for p in projects]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.manage_projects)),
) -> ProjectResponse:
    """Create a new project (Admin and CTO, §7.3). A triage lead is required (BR-15)."""
    await validate_triage_lead(db, payload.triage_lead_id)
    # Check slug uniqueness
    existing = await db.execute(select(Project).where(Project.slug == payload.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slug '{payload.slug}' is already taken.",
        )

    project = Project(
        name=payload.name,
        slug=payload.slug,
        color=payload.color,
        description=payload.description,
        default_labels=payload.default_labels,
        triage_lead_id=payload.triage_lead_id,
        created_by_id=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _project_to_response(db, project)


@router.get("/{slug}", response_model=ProjectResponse, summary="Get project by slug")
async def get_project(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Return a single project identified by its slug."""
    project = await _get_project_or_404(db, slug)
    return await _project_to_response(db, project)


@router.patch("/{slug}", response_model=ProjectResponse, summary="Update project")
async def update_project(
    slug: str,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.manage_projects)),
) -> ProjectResponse:
    """Partially update a project's metadata."""
    project = await _get_project_or_404(db, slug)
    await _apply_project_update(db, project, payload.model_dump(exclude_unset=True))
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _project_to_response(db, project)


@router.delete(
    "/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a project",
)
async def archive_project(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.manage_projects)),
) -> None:
    """Soft-delete a project by setting ``archived_at``."""
    project = await _get_project_or_404(db, slug)
    project.archived_at = datetime.now(tz=timezone.utc)
    db.add(project)
    await db.commit()


# ── ID-based routes for frontend compatibility ───────────────────────────────────

@router.get(
    "/id/{project_id}",
    response_model=ProjectResponse,
    summary="Get project by ID",
    include_in_schema=False,  # Keep slug as primary, hide from docs
)
async def get_project_by_id(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Return a single project identified by its ID (UUID)."""
    try:
        project_int_id = int(project_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project ID format")
    result = await db.execute(select(Project).where(Project.id == project_int_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project not found")
    return await _project_to_response(db, project)


@router.patch(
    "/id/{project_id}",
    response_model=ProjectResponse,
    summary="Update project by ID",
    include_in_schema=False,
)
async def update_project_by_id(
    project_id: str,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.manage_projects)),
) -> ProjectResponse:
    """Partially update a project's metadata by ID."""
    try:
        project_int_id = int(project_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project ID format")
    result = await db.execute(select(Project).where(Project.id == project_int_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project not found")
    await _apply_project_update(db, project, payload.model_dump(exclude_unset=True))
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _project_to_response(db, project)


@router.post(
    "/id/{project_id}/archive",
    response_model=ProjectResponse,
    summary="Archive a project by ID",
    include_in_schema=False,
)
async def archive_project_by_id(
    project_id: str,
    payload: ProjectArchiveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_action(Action.manage_projects)),
) -> ProjectResponse:
    """Archive or restore a project by ID."""
    try:
        project_int_id = int(project_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid project ID format")
    result = await db.execute(select(Project).where(Project.id == project_int_id))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project not found")
    if payload.archive:
        project.archived_at = datetime.now(tz=timezone.utc)
    else:
        project.archived_at = None
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return await _project_to_response(db, project)


# ── Releases and the Stream (nested under projects, slice 09) ────────────────
# ``{ref}`` is the project's slug or its numeric id.

@router.get(
    "/{ref}/releases",
    response_model=List[ReleaseResponse],
    summary="List releases for a project",
)
async def list_releases(
    ref: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> List[ReleaseResponse]:
    """Every release of a project, most recent first — never its Stream (08a)."""
    authorize(current_user, Action.view_releases)
    from app.api.v1.releases import _release_to_response

    project = await _get_project_or_404(db, ref)
    result = await db.execute(
        select(Release)
        .where(
            Release.project_id == project.id,
            Release.kind == ReleaseKind.release.value,
            Release.deleted_at.is_(None),
        )
        .order_by(Release.created_at.desc())
    )
    return [
        await _release_to_response(db, r, current_user, now) for r in result.scalars().all()
    ]


@router.post(
    "/{ref}/releases",
    response_model=ReleaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a release",
)
async def create_release(
    ref: str,
    payload: ProjectReleaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    """Create a release under the project; it starts in Planning (FR-49)."""
    from app.api.v1.releases import _respond
    from app.services.release_service import release_service

    project = await _get_project_or_404(db, ref)
    authorize(current_user, Action.manage_releases, project_target(project))
    release = await release_service.create(db, project, payload.model_dump(), current_user)
    return await _respond(db, release, current_user, now)


@router.get("/{ref}/stream", response_model=ReleaseResponse, summary="The project's Stream")
async def get_stream(
    ref: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    """The Stream (FR-46, FR-47); its board is ``GET /releases/{id}/board``."""
    authorize(current_user, Action.view_releases)
    from app.api.v1.releases import _release_to_response

    project = await _get_project_or_404(db, ref)
    return await _release_to_response(db, await stream_of(db, project.id), current_user, now)


@router.get(
    "/{ref}/releases/{version}",
    response_model=ReleaseResponse,
    summary="Get a specific release",
)
async def get_release(
    ref: str,
    version: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    now: datetime = Depends(get_now),
) -> ReleaseResponse:
    """Return a single release identified by project + version string."""
    authorize(current_user, Action.view_releases)
    from app.api.v1.releases import _release_to_response

    release = await _get_release_or_404(db, ref, version)
    return await _release_to_response(db, release, current_user, now)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_project_or_404(db: AsyncSession, ref: str) -> Project:
    """A project by slug, or by id when ``ref`` is all digits and no slug matches."""
    project = (await db.execute(select(Project).where(Project.slug == ref))).scalar_one_or_none()
    if project is None and ref.isdigit():
        project = await db.get(Project, int(ref))
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{ref}' not found")
    return project


async def _get_release_or_404(db: AsyncSession, ref: str, version: str) -> Release:
    project = await _get_project_or_404(db, ref)
    result = await db.execute(
        select(Release).where(
            Release.project_id == project.id,
            Release.version == version,
            Release.kind == ReleaseKind.release.value,
            Release.deleted_at.is_(None),
        )
    )
    release = result.scalar_one_or_none()
    if release is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Release '{version}' not found in project '{ref}'",
        )
    return release
