"""Project and nested release endpoints.

GET    /projects                              — list projects
POST   /projects                              — create project
GET    /projects/{slug}                       — get project detail
PATCH  /projects/{slug}                       — update project
DELETE /projects/{slug}                       — archive project
GET    /projects/{slug}/releases              — list releases for project
POST   /projects/{slug}/releases              — create release
GET    /projects/{slug}/releases/{version}    — get release detail
PATCH  /projects/{slug}/releases/{version}    — update release
POST   /projects/{slug}/releases/{version}/go-nogo — submit go/no-go decision
"""

from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_role
from app.db.models.project import Project
from app.db.models.release import Release, GoNogoStatus
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.schemas.project import ProjectArchiveRequest, ProjectCreate, ProjectResponse, ProjectUpdate
from app.schemas.release import GoNogoRequest, ReleaseCreate, ReleaseResponse, ReleaseUpdate

router = APIRouter()


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
    return [ProjectResponse.model_validate(p) for p in projects]


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a project",
)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cto)),
) -> ProjectResponse:
    """Create a new project (admin / CTO only)."""
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
        description=payload.description,
        default_labels=payload.default_labels,
        created_by_id=current_user.id,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("/{slug}", response_model=ProjectResponse, summary="Get project by slug")
async def get_project(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProjectResponse:
    """Return a single project identified by its slug."""
    project = await _get_project_or_404(db, slug)
    return ProjectResponse.model_validate(project)


@router.patch("/{slug}", response_model=ProjectResponse, summary="Update project")
async def update_project(
    slug: str,
    payload: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cto)),
) -> ProjectResponse:
    """Partially update a project's metadata."""
    project = await _get_project_or_404(db, slug)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete(
    "/{slug}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Archive a project",
)
async def archive_project(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
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
    return ProjectResponse.model_validate(project)


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
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cto)),
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
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


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
    current_user: User = Depends(require_role(UserRole.admin)),
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
    return ProjectResponse.model_validate(project)


# ── Releases (nested under projects) ─────────────────────────────────────────

@router.get(
    "/{slug}/releases",
    response_model=List[ReleaseResponse],
    summary="List releases for a project",
)
async def list_releases(
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ReleaseResponse]:
    """Return all releases for a project, most recent first."""
    from app.api.v1.releases import _release_to_response

    project = await _get_project_or_404(db, slug)
    result = await db.execute(
        select(Release)
        .where(Release.project_id == project.id)
        .order_by(Release.created_at.desc())
    )
    releases = result.scalars().all()
    return [await _release_to_response(db, r) for r in releases]


@router.post(
    "/{slug}/releases",
    response_model=ReleaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a release",
)
async def create_release(
    slug: str,
    payload: ReleaseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cto, UserRole.triage_lead)),
) -> ReleaseResponse:
    """Create a new release under the given project."""
    from app.api.v1.releases import _release_to_response

    project = await _get_project_or_404(db, slug)
    release = Release(
        project_id=project.id,
        version=payload.version,
        description=payload.description,
        target_date=payload.target_date,
        staging_url=payload.staging_url,
        created_by_id=current_user.id,
    )
    db.add(release)
    await db.commit()
    await db.refresh(release)
    return await _release_to_response(db, release)


@router.get(
    "/{slug}/releases/{version}",
    response_model=ReleaseResponse,
    summary="Get a specific release",
)
async def get_release(
    slug: str,
    version: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReleaseResponse:
    """Return a single release identified by project slug + version string."""
    from app.api.v1.releases import _release_to_response

    release = await _get_release_or_404(db, slug, version)
    return await _release_to_response(db, release)


@router.patch(
    "/{slug}/releases/{version}",
    response_model=ReleaseResponse,
    summary="Update release metadata",
)
async def update_release(
    slug: str,
    version: str,
    payload: ReleaseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cto, UserRole.triage_lead)),
) -> ReleaseResponse:
    """Partially update a release (status, staging URL, description, target date)."""
    from app.api.v1.releases import _release_to_response

    release = await _get_release_or_404(db, slug, version)
    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(release, field, value)
    db.add(release)
    await db.commit()
    await db.refresh(release)
    return await _release_to_response(db, release)


@router.post(
    "/{slug}/releases/{version}/go-nogo",
    response_model=ReleaseResponse,
    summary="Submit go/no-go decision",
)
async def submit_go_nogo(
    slug: str,
    version: str,
    payload: GoNogoRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.cto, UserRole.admin)),
) -> ReleaseResponse:
    """Record a go or no-go gate decision for a release (CTO / admin only)."""
    from app.api.v1.releases import _release_to_response

    release = await _get_release_or_404(db, slug, version)
    release.go_nogo_status = payload.decision
    release.go_nogo_note = payload.note
    release.go_nogo_by_id = current_user.id
    release.go_nogo_at = datetime.now(tz=timezone.utc)
    db.add(release)
    await db.commit()
    await db.refresh(release)

    # Notify team via Celery task
    template = "release_approved" if payload.decision == GoNogoStatus.approved else "release_blocked"
    from app.tasks.notifications import bulk_notify_team
    # (enqueue Telegram alerts for triage leads / QA team)

    return await _release_to_response(db, release)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_project_or_404(db: AsyncSession, slug: str) -> Project:
    result = await db.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project '{slug}' not found")
    return project


async def _get_release_or_404(db: AsyncSession, slug: str, version: str) -> Release:
    project = await _get_project_or_404(db, slug)
    result = await db.execute(
        select(Release).where(
            Release.project_id == project.id,
            Release.version == version,
        )
    )
    release = result.scalar_one_or_none()
    if release is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Release '{version}' not found in project '{slug}'",
        )
    return release
