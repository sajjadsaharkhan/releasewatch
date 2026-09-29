"""Containers — where an item is placed (08a Part 1, PRD v3 §8.1).

Placement is one column, ``issues.release_id``: the project's Stream, one of
its Releases, or null for the backlog. ``resolve`` is the one check every
placement path (create, triage accept, PATCH, bulk move) goes through.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.models.issue import Issue, IssueStatus
from app.db.models.release import Release, ReleaseKind


def _value(v):
    return getattr(v, "value", v)


async def resolve(db: AsyncSession, project_id: int, release_id: int | None) -> Release | None:
    """Return the container ``release_id`` names for an item of ``project_id``,
    ``None`` for the backlog, or raise.

    - 404 when it doesn't exist (or was deleted);
    - 409 ``release_project_mismatch`` when it's another project's;
    - 409 ``release_closed`` for a Release that is Released or Cancelled.
    """
    if release_id is None:
        return None
    release = await db.get(Release, int(release_id))
    if release is None or release.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")
    if release.project_id != project_id:
        raise DomainError(
            status.HTTP_409_CONFLICT,
            "That release belongs to a different project.",
            "release_project_mismatch",
        )
    if release.is_closed:
        raise DomainError(
            status.HTTP_409_CONFLICT,
            f"{release.version} is {_value(release.status)} and takes no new items.",
            "release_closed",
        )
    return release


async def stream_of(db: AsyncSession, project_id: int) -> Release:
    """The project's Stream (every project has exactly one, BR-51)."""
    return (await db.execute(
        select(Release).where(
            Release.project_id == project_id, Release.kind == ReleaseKind.stream.value,
        )
    )).scalar_one()


def ensure_movable(issue: Issue, new_release_id: int | None) -> None:
    """A Done item never changes container (BR-54, AC-58)."""
    if new_release_id == issue.release_id:
        return
    if _value(issue.status) == IssueStatus.done.value:
        raise DomainError(
            status.HTTP_409_CONFLICT,
            "A Done item can't move to another container.",
            "done_item_immobile",
        )


def ensure_blocker_allowed(item_type: str, container: Release | None) -> None:
    """The release blocker flag only exists on a bug in a Release (BR-58, AC-65)."""
    if container is None or container.is_stream:
        raise DomainError(
            status.HTTP_409_CONFLICT,
            "Only a bug in a release can block it.",
            "release_blocker_release_only",
        )
    if item_type != "bug":
        raise DomainError(
            status.HTTP_409_CONFLICT,
            "Only a bug can block a release.",
            "release_blocker_release_only",
        )


def stream_immutable() -> DomainError:
    """The Stream can't be renamed, cancelled, archived, or deleted (FR-46)."""
    return DomainError(
        status.HTTP_409_CONFLICT,
        "The Stream can't be edited, cancelled, archived, or deleted.",
        "stream_immutable",
    )
