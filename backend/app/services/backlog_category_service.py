"""BacklogCategoryService — a project's backlog categories (2026-09-28 decisions).

- Every project has one fixed **Default** (``is_default``): created with the
  project, always first, never renamed, recoloured, moved or deleted.
- CTO and Admin add, edit, reorder and delete the others (Policy
  ``manage_backlog_categories``). Names are unique per project ignoring case
  (≤ 40 chars); a project holds at most 20 categories, Default included.
  Icons and colours come from the curated sets in ``models/backlog_category``.
- Deleting a category moves every item that uses it — open, done, in a
  release, even soft-deleted — to the project's Default, writing one
  ``backlog_category_changed`` timeline entry per item and sending no
  notification. The move doesn't count as touching the item (``updated_at``
  is kept), like re-ranking.
- ``resolve`` is the one place an item's category is chosen: none given →
  the project's Default; one given → it must belong to the item's project.
"""

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.models.backlog_category import MAX_CATEGORIES_PER_PROJECT, BacklogCategory
from app.db.models.issue import Issue
from app.db.models.issue_timeline import TimelineEventType
from app.db.models.project import Project
from app.db.models.user import User


def snapshot(category: BacklogCategory) -> dict:
    """What a timeline entry records about a category — kept as it was, so
    history still reads right after a rename or delete."""
    return {
        "id": category.id,
        "name": category.name,
        "icon": category.icon,
        "color": category.color,
        "is_default": category.is_default,
    }


def _locked() -> DomainError:
    return DomainError(
        status.HTTP_409_CONFLICT,
        "The Default category is fixed — it can't be renamed, restyled, moved or deleted.",
        "default_category_locked",
    )


class BacklogCategoryService:
    # ── Reads ────────────────────────────────────────────────────────────────

    @staticmethod
    async def list_with_counts(
        db: AsyncSession, project_id: int
    ) -> list[tuple[BacklogCategory, int]]:
        """The project's categories in order (Default first), each with its item count."""
        counts = (
            select(Issue.backlog_category_id, func.count(Issue.id).label("n"))
            .where(Issue.project_id == project_id, Issue.deleted_at.is_(None))
            .group_by(Issue.backlog_category_id)
            .subquery()
        )
        rows = (
            await db.execute(
                select(BacklogCategory, func.coalesce(counts.c.n, 0))
                .outerjoin(counts, counts.c.backlog_category_id == BacklogCategory.id)
                .where(BacklogCategory.project_id == project_id)
                .order_by(
                    BacklogCategory.is_default.desc(),
                    BacklogCategory.position.asc(),
                    BacklogCategory.id.asc(),
                )
            )
        ).all()
        return [(c, n) for c, n in rows]

    @staticmethod
    async def ordered(db: AsyncSession, project_id: int) -> list[BacklogCategory]:
        return list(
            (
                await db.execute(
                    select(BacklogCategory)
                    .where(BacklogCategory.project_id == project_id)
                    .order_by(
                        BacklogCategory.is_default.desc(),
                        BacklogCategory.position.asc(),
                        BacklogCategory.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )

    @staticmethod
    async def default_for(db: AsyncSession, project_id: int) -> BacklogCategory:
        category = (
            await db.execute(
                select(BacklogCategory).where(
                    BacklogCategory.project_id == project_id,
                    BacklogCategory.is_default.is_(True),
                )
            )
        ).scalar_one_or_none()
        if category is None:  # pragma: no cover — every project gets one on insert
            raise RuntimeError(f"project {project_id} has no Default backlog category")
        return category

    async def resolve(
        self,
        db: AsyncSession,
        project_id: int,
        category_id: int | None,
    ) -> BacklogCategory:
        """The category an item in ``project_id`` gets: ``category_id`` if it is
        one of the project's (422 ``category_not_in_project`` otherwise), else Default."""
        if category_id is None:
            return await self.default_for(db, project_id)
        category = await db.get(BacklogCategory, int(category_id))
        if category is None or category.project_id != project_id:
            raise DomainError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "That category isn't one of this project's backlog categories.",
                "category_not_in_project",
                errors={"backlog_category_id": "Not a category of this project."},
            )
        return category

    async def get(self, db: AsyncSession, project_id: int, category_id: int) -> BacklogCategory:
        category = await db.get(BacklogCategory, category_id)
        if category is None or category.project_id != project_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
        return category

    # ── Writes ───────────────────────────────────────────────────────────────

    @staticmethod
    async def _ensure_name_free(
        db: AsyncSession,
        project_id: int,
        name: str,
        exclude_id: int | None = None,
    ) -> None:
        q = select(BacklogCategory.id).where(
            BacklogCategory.project_id == project_id,
            func.lower(BacklogCategory.name) == name.lower(),
        )
        if exclude_id is not None:
            q = q.where(BacklogCategory.id != exclude_id)
        if (await db.execute(q)).first() is not None:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                f"This project already has a category called “{name}”.",
                "category_name_taken",
                errors={"name": "Already used in this project."},
            )

    async def create(
        self,
        db: AsyncSession,
        project: Project,
        *,
        name: str,
        icon: str,
        color: str,
    ) -> BacklogCategory:
        # Serialize writes per project so the limit and positions can't race.
        await db.execute(select(Project.id).where(Project.id == project.id).with_for_update())
        count, last = (
            await db.execute(
                select(func.count(BacklogCategory.id), func.max(BacklogCategory.position)).where(
                    BacklogCategory.project_id == project.id
                )
            )
        ).one()
        if count >= MAX_CATEGORIES_PER_PROJECT:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                f"A project can have at most {MAX_CATEGORIES_PER_PROJECT} backlog categories.",
                "category_limit_reached",
            )
        await self._ensure_name_free(db, project.id, name)
        category = BacklogCategory(
            project_id=project.id,
            name=name,
            icon=icon,
            color=color,
            position=(last or 0) + 1,
            is_default=False,
        )
        db.add(category)
        await db.flush()
        return category

    async def update(
        self,
        db: AsyncSession,
        project: Project,
        category_id: int,
        changes: dict,
    ) -> BacklogCategory:
        category = await self.get(db, project.id, category_id)
        if category.is_default:
            raise _locked()
        if "name" in changes and changes["name"] != category.name:
            await self._ensure_name_free(db, project.id, changes["name"], exclude_id=category.id)
        for field in ("name", "icon", "color"):
            if field in changes and changes[field] is not None:
                setattr(category, field, changes[field])
        db.add(category)
        await db.flush()
        return category

    async def reorder(self, db: AsyncSession, project: Project, ids: list[int]) -> None:
        """``ids`` is every non-Default category in its new order; Default stays first."""
        await db.execute(select(Project.id).where(Project.id == project.id).with_for_update())
        current = [c for c in await self.ordered(db, project.id) if not c.is_default]
        if sorted(ids) != sorted(c.id for c in current) or len(set(ids)) != len(ids):
            default = next((c for c in await self.ordered(db, project.id) if c.is_default), None)
            if default is not None and default.id in ids:
                raise _locked()
            raise DomainError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Send every category except Default, each once, in the new order.",
                "category_order_mismatch",
            )
        by_id = {c.id: c for c in current}
        for position, category_id in enumerate(ids, start=1):
            by_id[category_id].position = position
            db.add(by_id[category_id])
        await db.flush()

    async def delete(
        self,
        db: AsyncSession,
        project: Project,
        category_id: int,
        actor: User,
    ) -> int:
        """Move the category's items to Default, then delete it. Returns how many moved."""
        from app.services.timeline_service import TimelineService

        category = await self.get(db, project.id, category_id)
        if category.is_default:
            raise _locked()
        default = await self.default_for(db, project.id)

        moved_ids = list(
            (
                await db.execute(
                    select(Issue.id)
                    .where(Issue.backlog_category_id == category.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        if moved_ids:
            await db.execute(
                update(Issue)
                .where(Issue.id.in_(moved_ids))
                .values(backlog_category_id=default.id, updated_at=Issue.updated_at)
                .execution_options(synchronize_session=False)
            )
            timeline = TimelineService()
            meta = {
                "from": snapshot(category),
                "to": snapshot(default),
                "reason": "category_deleted",
            }
            for issue_id in moved_ids:
                await timeline.create_event(
                    db=db,
                    issue_id=issue_id,
                    actor_id=actor.id,
                    event_type=TimelineEventType.backlog_category_changed,
                    body=None,
                    meta=meta,
                )
        await db.delete(category)
        await db.flush()
        return len(moved_ids)


backlog_category_service = BacklogCategoryService()
