"""BacklogService — backlog membership, the category rule, ranking, and bulk move.

Slice 08 (docs/phase-2/08-backlog-and-tech-debt.md, FR-23–25, BR-04–06).

**Membership is derived, never stored (BR-04).** An item is in its project's
backlog when it is not deleted, has no release, and holds a backlog status —
a board status other than Done (``BACKLOG_STATUSES``). New and Needs info are
triage; Done and Cancelled are finished. ``backlog_clause`` is the one place
that predicate is written; ``is_member`` is the same rule for a loaded row.

**Categories (2026-09-28).** Every item always has one of its project's
backlog categories — the project's Default unless another is chosen
(``BacklogCategoryService``). The old "category required on entering the
backlog" rule (BR-06) is gone from the UI; the database guarantees it instead.

**Ranking.** Midpoint insertion between neighbours; a new member goes to the
bottom (``max(rank) + RANK_STEP``). When splitting a gap would leave one
narrower than ``MIN_GAP``, the project's ranks are renumbered in one
statement first. Rank and category are kept when an item leaves the
backlog, so a demoted item returns where it was.
Rank writes never touch ``updated_at`` — reordering isn't activity on the
item, and the "untouched for over 6 months" hint reads ``updated_at``.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import DomainError
from app.db.models.backlog_category import BacklogCategory
from app.db.models.issue import BACKLOG_STATUSES, Issue, IssueType
from app.db.models.project import Project
from app.db.models.release import Release
from app.db.models.user import User

#: Gap between consecutive ranks for new members and after a renumber.
RANK_STEP = 1024.0
#: The narrowest gap a midpoint may leave; below it the project's ranks are renumbered.
MIN_GAP = 1e-6
#: The hygiene hint's threshold — "untouched for over 6 months" (display only).
STALE_AFTER = timedelta(days=182)

_BACKLOG_STATUS_VALUES = tuple(s.value for s in BACKLOG_STATUSES)

def _value(v):
    return getattr(v, "value", v)


# ── Membership ────────────────────────────────────────────────────────────────


def backlog_clause(include_tech_debt: bool = False):
    """The backlog predicate as SQL (BR-04) — every backlog read goes through it."""
    conditions = [
        Issue.deleted_at.is_(None),
        Issue.release_id.is_(None),
        Issue.status.in_(_BACKLOG_STATUS_VALUES),
    ]
    if not include_tech_debt:
        conditions.append(Issue.is_tech_debt.is_(False))
    return and_(*conditions)


def backlog_items(project_id: int, include_tech_debt: bool = False):
    """``select(Issue)`` for a project's backlog, in rank order."""
    return (
        select(Issue)
        .where(Issue.project_id == project_id, backlog_clause(include_tech_debt))
        .order_by(Issue.backlog_rank.asc().nulls_last(), Issue.created_at.asc(), Issue.id.asc())
    )


def is_member(
    *, release_id: int | None, status: str | None, deleted: bool = False,
) -> bool:
    """``backlog_clause`` for plain values — used to decide whether an edit makes
    an item *enter* the backlog before the edit is applied."""
    return not deleted and release_id is None and _value(status) in _BACKLOG_STATUS_VALUES


@dataclass
class BacklogPage:
    items: list[Issue]
    stale_ids: list[int]
    hidden_tech_debt_count: int


class BacklogService:

    # ── Ranking ──────────────────────────────────────────────────────────────

    @staticmethod
    async def bottom_rank(db: AsyncSession, project_id: int) -> float:
        """Rank for a new member: below every ranked item in the project."""
        current = (await db.execute(
            select(func.max(Issue.backlog_rank)).where(Issue.project_id == project_id)
        )).scalar_one_or_none()
        return (current or 0.0) + RANK_STEP

    async def place(self, db: AsyncSession, issue: Issue) -> None:
        """Give a backlog member without a rank one at the bottom. No-op otherwise."""
        if issue.backlog_rank is not None:
            return
        if not is_member(
            release_id=issue.release_id, status=issue.status,
            deleted=issue.deleted_at is not None,
        ):
            return
        issue.backlog_rank = await self.bottom_rank(db, issue.project_id)
        db.add(issue)

    @staticmethod
    async def _set_rank(db: AsyncSession, issue_id: int, rank: float) -> None:
        await db.execute(
            update(Issue)
            .where(Issue.id == issue_id)
            .values(backlog_rank=rank, updated_at=Issue.updated_at)
        )

    @staticmethod
    async def _renumber(db: AsyncSession, project_id: int) -> None:
        """Respread every ranked item in the project ``RANK_STEP`` apart, order kept."""
        ranked = (
            select(
                Issue.id.label("id"),
                func.row_number().over(
                    order_by=(Issue.backlog_rank.asc(), Issue.id.asc())
                ).label("rn"),
            )
            .where(Issue.project_id == project_id, Issue.backlog_rank.isnot(None))
            .subquery()
        )
        await db.execute(
            update(Issue)
            .where(Issue.id == ranked.c.id)
            .values(backlog_rank=ranked.c.rn * RANK_STEP, updated_at=Issue.updated_at)
        )

    async def _members(
        self, db: AsyncSession, project_id: int, exclude_id: int,
    ) -> list[tuple[int, float]]:
        """Every member (debt included) as ``(id, rank)``, in order.

        Members without a rank (older rows) are ranked at the bottom first."""
        rows = (await db.execute(
            backlog_items(project_id, include_tech_debt=True)
            .with_only_columns(Issue.id, Issue.backlog_rank)
        )).all()
        members: list[tuple[int, float]] = []
        for issue_id, rank in rows:
            if rank is None:
                rank = await self.bottom_rank(db, project_id)
                await self._set_rank(db, issue_id, rank)
            if issue_id != exclude_id:
                members.append((issue_id, rank))
        return members

    async def reorder(
        self,
        db: AsyncSession,
        project: Project,
        issue_id: int,
        *,
        before_id: int | None,
        after_id: int | None,
    ) -> float:
        """Move ``issue_id`` so it sits after ``after_id`` and/or before ``before_id``.

        ``after_id`` is the item that ends up directly above, ``before_id`` the
        one directly below. Given one, the other is its current neighbour;
        given both, the item goes between them. Returns the new rank.
        """
        # Serialize reorders within a project — two concurrent midpoints over the
        # same neighbours would otherwise produce equal ranks.
        await db.execute(select(Project.id).where(Project.id == project.id).with_for_update())

        moved = (await db.execute(
            select(Issue.id).where(Issue.id == issue_id, Issue.project_id == project.id,
                                   backlog_clause(include_tech_debt=True))
        )).scalar_one_or_none()
        if moved is None:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "That item isn't in this project's backlog.",
                "not_in_backlog",
            )

        for attempt in range(2):
            members = await self._members(db, project.id, exclude_id=issue_id)
            index = {mid: i for i, (mid, _) in enumerate(members)}
            for anchor in (before_id, after_id):
                if anchor is not None and anchor not in index:
                    raise DomainError(
                        status.HTTP_409_CONFLICT,
                        "The item to place it next to isn't in this project's backlog.",
                        "anchor_not_in_backlog",
                    )

            if after_id is not None and before_id is not None:
                upper, lower = index[after_id], index[before_id]
                if upper >= lower:
                    raise DomainError(
                        status.HTTP_409_CONFLICT,
                        "after_id must be above before_id.",
                        "invalid_anchors",
                    )
            elif after_id is not None:
                upper = index[after_id]
                lower = upper + 1 if upper + 1 < len(members) else None
            else:
                lower = index[before_id]
                upper = lower - 1 if lower > 0 else None

            upper_rank = members[upper][1] if upper is not None else None
            lower_rank = members[lower][1] if lower is not None else None

            if upper_rank is None:
                rank = lower_rank - RANK_STEP
            elif lower_rank is None:
                rank = upper_rank + RANK_STEP
            elif (lower_rank - upper_rank) / 2 >= MIN_GAP:
                # Both halves stay at least MIN_GAP wide.
                rank = (upper_rank + lower_rank) / 2
            elif attempt == 0:
                await self._renumber(db, project.id)
                continue
            else:  # pragma: no cover — a fresh renumber always leaves RANK_STEP gaps
                raise RuntimeError("backlog renumber left no gap")

            await self._set_rank(db, issue_id, rank)
            return rank
        raise RuntimeError("unreachable")  # pragma: no cover

    # ── Reads ────────────────────────────────────────────────────────────────

    async def page(
        self,
        db: AsyncSession,
        project_id: int,
        *,
        include_tech_debt: bool,
        now: datetime,
    ) -> BacklogPage:
        items = list((await db.execute(
            backlog_items(project_id, include_tech_debt).options(
                selectinload(Issue.assignee),
                selectinload(Issue.reporter),
                selectinload(Issue.release),
                selectinload(Issue.project),
            )
        )).scalars().all())
        stale_before = now - STALE_AFTER
        hidden = 0
        if not include_tech_debt:
            hidden = (await db.execute(
                select(func.count(Issue.id)).where(
                    Issue.project_id == project_id,
                    backlog_clause(include_tech_debt=True),
                    Issue.is_tech_debt.is_(True),
                )
            )).scalar_one()
        return BacklogPage(
            items=items,
            stale_ids=[i.id for i in items if i.updated_at and i.updated_at < stale_before],
            hidden_tech_debt_count=hidden,
        )

    # ── Bulk move (FR-25) ────────────────────────────────────────────────────

    async def bulk_move(
        self,
        db: AsyncSession,
        issues: dict[int, Issue | None],
        release: Release,
        actor: User,
    ) -> list[int]:
        """Move every item to container ``release`` (the Stream or a Release), or
        none (409 ``bulk_move_failed`` with
        per-item ``errors``). ``issues`` maps each requested id to the visible
        row, or ``None`` when the caller can't see it. Returns the moved ids."""
        from app.services.issue_service import issue_service

        errors: dict[str, str] = {}
        immobile: dict[str, str] = {}
        for issue_id, issue in issues.items():
            if issue is None:
                errors[str(issue_id)] = "Not found."
            elif issue.project_id != release.project_id:
                errors[str(issue_id)] = "It belongs to a different project than the release."
            elif _value(issue.status) == "done" and issue.release_id != release.id:
                immobile[str(issue_id)] = "It's Done — a Done item never moves."
        if immobile:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "No items were moved — Done items can't change container.",
                "done_item_immobile",
                errors={**errors, **immobile},
            )
        if errors:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "No items were moved — fix the items listed and try again.",
                "bulk_move_failed",
                errors=errors,
            )

        moved: list[int] = []
        for issue_id, issue in issues.items():
            if issue.release_id == release.id:
                continue
            await issue_service.update(db, issue_id, {"release_id": release.id}, actor)
            moved.append(issue_id)
        return moved


    async def bulk_set_category(
        self,
        db: AsyncSession,
        project: Project,
        issues: dict[int, Issue | None],
        category: BacklogCategory,
        actor: User,
    ) -> list[int]:
        """Give every item ``category``, or none (409 ``bulk_category_failed``
        with per-item ``errors``). Every item must be visible and in ``project``.
        Rank is untouched — only the item's group changes. Returns the changed ids."""
        from app.services.issue_service import issue_service

        errors: dict[str, str] = {}
        for issue_id, issue in issues.items():
            if issue is None:
                errors[str(issue_id)] = "Not found."
            elif issue.project_id != project.id:
                errors[str(issue_id)] = "It belongs to a different project."
        if errors:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "No categories were changed — fix the items listed and try again.",
                "bulk_category_failed",
                errors=errors,
            )

        updated: list[int] = []
        for issue_id, issue in issues.items():
            if issue.backlog_category_id == category.id:
                continue
            await issue_service.update(db, issue_id, {"backlog_category_id": category.id}, actor)
            updated.append(issue_id)
        return updated


async def get_release_or_404(db: AsyncSession, release_id: int) -> Release:
    release = await db.get(Release, release_id)
    if release is None or getattr(release, "deleted_at", None) is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")
    return release


def tech_debt_clause():
    """Items on the Technical debt page: flagged tasks (BR-36) that aren't deleted."""
    return and_(
        Issue.deleted_at.is_(None),
        Issue.is_tech_debt.is_(True),
        Issue.type == IssueType.task.value,
    )


backlog_service = BacklogService()
