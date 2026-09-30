"""CycleService — the only writer of ``issue_cycles`` and ``issues.current_cycle_id``.

docs/phase-2/cycle-model.md, 08a Part 2. ``IssueService`` (and, through it,
triage and merges) call it; nothing else touches cycles.

- A cycle exists only while the item has a container. Placing an item
  (create, triage accept, a move out of the backlog) starts cycle 1,
  ``planned``. Moving it to the backlog deletes every cycle (CY-14).
- While the item isn't Done, its open cycle follows it between containers (CY-01).
- Status moves stamp the current cycle: first In progress → ``picked_up_at``;
  first To review or In review, whichever comes first (09a) → ``submitted_at``
  and ``delivered_by_id`` = the assignee, never the actor (CY-05); Done from
  To review or In review → ``verified_at``; Cancelled → ``closed_at``.
- ``start_return`` closes the current cycle and opens the next one with the
  reason the work came back.

Invariant: ``issues.current_cycle_id IS NULL`` ⇔ ``issues.release_id IS NULL``.
"""

from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue import REVIEW_STATUSES, Issue, IssueStatus
from app.db.models.issue_cycle import CycleStartReason, IssueCycle
from app.db.models.release import Release
from app.db.models.user import User


def _value(v):
    return getattr(v, "value", v)


def return_reason_for_done(container: Release) -> CycleStartReason:
    """Where a problem with a Done item was caught (cycle-model §3): in a Release
    that hasn't shipped it's release QA; in the Stream, or in a Released release,
    the work is on production."""
    if not container.is_stream and not container.is_shipped:
        return CycleStartReason.release_qa
    return CycleStartReason.production


class CycleService:

    @staticmethod
    async def current(db: AsyncSession, issue: Issue) -> IssueCycle | None:
        if issue.current_cycle_id is None:
            return None
        return await db.get(IssueCycle, issue.current_cycle_id)

    # ── Placement ────────────────────────────────────────────────────────────

    async def on_placed(
        self, db: AsyncSession, issue: Issue, actor: User | None, *, now: datetime | None = None,
    ) -> IssueCycle | None:
        """The item got a container and has no current cycle → cycle 1, ``planned``."""
        if issue.release_id is None or issue.current_cycle_id is not None:
            return None
        await db.flush()
        cycle = IssueCycle(
            issue_id=issue.id,
            cycle_number=1,
            release_id=issue.release_id,
            start_reason=CycleStartReason.planned.value,
            start_by_id=actor.id if actor is not None else None,
            assignee_id=issue.assignee_id,
            started_at=now or datetime.now(tz=UTC),
        )
        db.add(cycle)
        await db.flush()
        issue.current_cycle_id = cycle.id
        db.add(issue)
        return cycle

    async def on_container_changed(self, db: AsyncSession, issue: Issue) -> None:
        """Container → container while the cycle is open: the cycle follows the
        item. A Done item never moves (BR-54), so delivered work keeps its container."""
        cycle = await self.current(db, issue)
        if cycle is None or issue.release_id is None:
            return
        if _value(issue.status) == IssueStatus.done.value:
            return
        cycle.release_id = issue.release_id
        db.add(cycle)

    async def on_moved_to_backlog(self, db: AsyncSession, issue: Issue) -> None:
        """Delete every cycle of the item (CY-14) — pointer first, then the rows."""
        issue.current_cycle_id = None
        db.add(issue)
        await db.flush()
        await db.execute(delete(IssueCycle).where(IssueCycle.issue_id == issue.id))

    async def after_container_change(
        self, db: AsyncSession, issue: Issue, old_release_id: int | None, actor: User | None,
    ) -> None:
        """Dispatch a change of ``issue.release_id`` to the right hook."""
        new = issue.release_id
        if new == old_release_id:
            return
        if new is None:
            await self.on_moved_to_backlog(db, issue)
        elif old_release_id is None or issue.current_cycle_id is None:
            await self.on_placed(db, issue, actor)
        else:
            await self.on_container_changed(db, issue)

    # ── Assignment and status ────────────────────────────────────────────────

    async def on_assignee(self, db: AsyncSession, issue: Issue) -> None:
        """Reassignment keeps updating the cycle's ``assignee_id`` (not attribution)."""
        cycle = await self.current(db, issue)
        if cycle is not None:
            cycle.assignee_id = issue.assignee_id
            db.add(cycle)

    async def on_status(
        self,
        db: AsyncSession,
        issue: Issue,
        from_status: IssueStatus,
        to_status: IssueStatus,
        actor: User,
        now: datetime,
    ) -> None:
        cycle = await self.current(db, issue)
        if cycle is None or from_status == to_status:
            return
        if to_status == IssueStatus.in_progress and cycle.picked_up_at is None:
            cycle.picked_up_at = now
        elif to_status in REVIEW_STATUSES and cycle.submitted_at is None:
            cycle.submitted_at = now
            # CY-05: the assignee at this moment — never the actor, and no
            # fallback to the actor when nobody is assigned.
            cycle.delivered_by_id = issue.assignee_id
        elif (
            to_status == IssueStatus.done
            and from_status in REVIEW_STATUSES
            and cycle.verified_at is None
        ):
            cycle.verified_at = now
        elif to_status == IssueStatus.cancelled:
            cycle.closed_at = now
        if from_status == IssueStatus.cancelled and to_status != IssueStatus.cancelled:
            # Restored from Cancelled (free workflow): the cycle is open again.
            cycle.closed_at = None
        db.add(cycle)

    # ── Returns ──────────────────────────────────────────────────────────────

    async def start_return(
        self,
        db: AsyncSession,
        issue: Issue,
        reason: CycleStartReason,
        actor: User,
        *,
        comment_id: int | None = None,
        merged_issue_id: int | None = None,
        now: datetime | None = None,
    ) -> IssueCycle | None:
        """Close the current cycle and open cycle N+1 with ``reason``.

        Call it after the item has its final container for the new cycle. An
        item with no container has no cycle to return from — returns ``None``.
        """
        if issue.release_id is None:
            return None
        now = now or datetime.now(tz=UTC)
        current = await self.current(db, issue)
        if current is not None and current.closed_at is None:
            current.closed_at = now
            db.add(current)
        last = (await db.execute(
            select(func.max(IssueCycle.cycle_number)).where(IssueCycle.issue_id == issue.id)
        )).scalar_one_or_none() or 0
        cycle = IssueCycle(
            issue_id=issue.id,
            cycle_number=last + 1,
            release_id=issue.release_id,
            start_reason=_value(reason),
            start_comment_id=comment_id,
            start_merged_issue_id=merged_issue_id,
            start_by_id=actor.id,
            assignee_id=issue.assignee_id,
            started_at=now,
        )
        db.add(cycle)
        await db.flush()
        issue.current_cycle_id = cycle.id
        db.add(issue)
        await db.flush()
        return cycle


cycle_service = CycleService()
