"""QueueService — every person's one ordered list of open work (slice 10).

The sole writer of ``queue_entries`` and ``queue_history``. Ordering rules
live in the pure ``app/queue_order.py``; this module loads entries, asks it
where things go, and writes the positions back.

``sync(db, issue)`` keeps queues in step with items. ``IssueService`` calls
it after every change to an item's assignee, status or priority (create,
``transition``, ``update``); it is state-based, so calling it twice is safe.
Automatic insertions and removals are never written to queue history — only
the human actions (``move``, ``pin``, ``unpin``) are (BR-44).
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from fastapi import status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app import queue_order
from app.core.errors import DomainError
from app.db.models.inbox_item import InboxEventType
from app.db.models.issue import BOARD_STATUSES, Issue, IssueStatus
from app.db.models.issue_cycle import IssueCycle
from app.db.models.label import Label
from app.db.models.queue import QueueAction, QueueEntry, QueueHistory
from app.db.models.user import User, UserRole
from app.policy import ASSIGNABLE_ROLES
from app.queue_order import PIN_LIMIT, QueueItem, QueueRuleError
from app.schemas.issue import UserSummary
from app.schemas.queue import (
    CardContainer,
    CardLabel,
    CardProject,
    WorkItemCard,
    WorkloadCounts,
    WorkloadRow,
)

#: Statuses an assigned item is queued in (BR-38): the board, minus Done.
#: New/Needs info (triage) and Cancelled are never queued.
QUEUE_STATUSES = tuple(s for s in BOARD_STATUSES if s != IssueStatus.done)
_QUEUE_VALUES = frozenset(s.value for s in QUEUE_STATUSES)

#: Namespace for the per-owner advisory lock (``_lock_queue``) — any constant
#: unique to queues; the second key is the owner's user id.
QUEUE_LOCK_NS = 10_010

#: How many upcoming queue items the Workload view shows per person (FR-43).
WORKLOAD_NEXT = 3

#: ``due_state == "soon"`` when the due date is at most this many days away.
DUE_SOON_DAYS = 2


@dataclass
class _Workload:
    """One person's tally while building the Workload view."""

    in_progress: list[int] = field(default_factory=list)
    next: list[int] = field(default_factory=list)
    open: int = 0
    pinned: int = 0


def _value(v):
    return getattr(v, "value", v)


def due_state(due: date | None, now: datetime) -> str:
    """``overdue`` past the due date, ``soon`` within 2 days, else ``none`` (FR-42)."""
    if due is None:
        return "none"
    today = now.astimezone(UTC).date()
    if due < today:
        return "overdue"
    if due <= today + timedelta(days=DUE_SOON_DAYS):
        return "soon"
    return "none"


def _item(entry: QueueEntry, issue: Issue) -> QueueItem:
    return QueueItem(
        issue_id=issue.id,
        priority=_value(issue.priority),
        due_date=issue.due_date,
        recurrence_count=issue.recurrence_count or 1,
        created_at=issue.created_at,
        pinned=entry.is_pinned,
        position=entry.position,
    )


def _refused(err: QueueRuleError) -> DomainError:
    code = status.HTTP_404_NOT_FOUND if err.code == "not_in_queue" else (
        status.HTTP_422_UNPROCESSABLE_ENTITY if err.code == "invalid_move"
        else status.HTTP_409_CONFLICT
    )
    return DomainError(code, err.detail, err.code)


async def build_cards(
    db: AsyncSession,
    issues: list[Issue],
    now: datetime,
    entries: dict[int, QueueEntry] | None = None,
) -> list[WorkItemCard]:
    """``WorkItemCard`` for each issue. Issues need ``project``, ``release``,
    ``reporter`` and ``assignee`` loaded (``card_load_options``)."""
    entries = entries or {}
    cycle_ids = [i.current_cycle_id for i in issues if i.current_cycle_id is not None]
    cycles: dict[int, IssueCycle] = {}
    if cycle_ids:
        rows = await db.execute(select(IssueCycle).where(IssueCycle.id.in_(cycle_ids)))
        cycles = {c.id: c for c in rows.scalars().all()}

    label_names = {n for i in issues for n in (i.labels or [])}
    label_colors: dict[str, str] = {}
    if label_names:
        rows = await db.execute(select(Label.name, Label.color).where(Label.name.in_(label_names)))
        label_colors = dict(rows.all())

    cards = []
    for issue in issues:
        cycle = cycles.get(issue.current_cycle_id)
        rejected = _value(issue.status) == IssueStatus.rejected.value
        entry = entries.get(issue.id)
        release = issue.release
        cards.append(WorkItemCard(
            id=issue.id,
            issue_number=issue.issue_number,
            type=issue.type,
            title=issue.title,
            project=CardProject(
                id=issue.project.id, slug=issue.project.slug,
                name=issue.project.name, color=issue.project.color,
            ),
            status=issue.status,
            priority=issue.priority,
            recurrence_count=issue.recurrence_count or 1,
            due_date=issue.due_date,
            due_state=due_state(issue.due_date, now),
            is_tech_debt=issue.is_tech_debt,
            is_release_blocker=issue.is_release_blocker,
            pinned=bool(entry and entry.is_pinned),
            pin_locked=bool(entry and entry.is_pinned and entry.pin_locked),
            cycle_number=cycle.cycle_number if cycle is not None else None,
            cycle_count=cycle.cycle_number if cycle is not None else 0,
            reject_reason=_value(cycle.start_reason) if cycle is not None and rejected else None,
            reject_comment_id=cycle.start_comment_id if cycle is not None and rejected else None,
            container=(
                CardContainer(
                    kind=_value(release.kind), name=release.version,
                    status=_value(release.status),
                )
                if release is not None else None
            ),
            labels=[
                CardLabel(name=n, color=label_colors[n])
                for n in (issue.labels or []) if n in label_colors
            ],
            reporter=UserSummary.model_validate(issue.reporter) if issue.reporter else None,
            assignee=UserSummary.model_validate(issue.assignee) if issue.assignee else None,
            created_at=issue.created_at,
            completed_at=issue.completed_at,
        ))
    return cards


def card_load_options():
    return (
        selectinload(Issue.project), selectinload(Issue.release),
        selectinload(Issue.reporter), selectinload(Issue.assignee),
    )


async def _lock_queue(db: AsyncSession, owner_id: int) -> None:
    """Serialise every write to one owner's queue until the transaction ends.

    Positions are computed from the neighbours a transaction reads; two
    concurrent inserts or moves into the same queue would otherwise place
    items from stale reads (seen with parallel E2E workers).
    """
    await db.execute(select(func.pg_advisory_xact_lock(QUEUE_LOCK_NS, owner_id)))


class QueueService:
    # ── Keeping queues in step with items ──────────────────────────────────────

    async def sync(
        self, db: AsyncSession, issue: Issue, *, priority_changed: bool = False,
    ) -> None:
        """Bring ``issue``'s queue entry in line with its assignee and status.

        - Assignee changed, or the item left the board (triage, Cancelled,
          unassigned, deleted): the entry leaves the old queue, pin released (BR-45).
        - Done: the pin is released (BR-46) and the entry goes dormant, keeping
          its rest-group position; a pinned one moves to the top of the rest
          first, so a return lands directly below the pins (FR-64).
        - Back from Done to the same assignee: the dormant entry wakes at its
          old position — always in the rest group, so never above a pin (BR-61).
        - Newly queued (no entry, or a new assignee): default rule (FR-39).
        - Priority changed on an unpinned entry: re-placed by the default rule.
        A reject from To review / In review changes nothing: it never left.
        """
        owner_id = issue.assignee_id
        if owner_id is not None:
            await _lock_queue(db, owner_id)
        entry = (await db.execute(
            select(QueueEntry).where(QueueEntry.issue_id == issue.id)
        )).scalar_one_or_none()
        current = _value(issue.status)
        live = owner_id is not None and issue.deleted_at is None

        if entry is not None and entry.user_id != owner_id:
            await db.delete(entry)
            await db.flush()
            entry = None

        if live and current in _QUEUE_VALUES:
            if entry is None:
                await self._insert(db, owner_id, issue)
            elif entry.left_at is not None:
                entry.left_at = None
                db.add(entry)
            elif priority_changed and not entry.is_pinned:
                await self._place_by_default(db, entry, issue)
        elif live and current == IssueStatus.done.value:
            if entry is not None and entry.left_at is None:
                if entry.is_pinned:
                    self._clear_pin(entry)
                    await self._set_position(db, entry, 0)
                entry.left_at = datetime.now(tz=UTC)
                db.add(entry)
        elif entry is not None:
            await db.delete(entry)
        await db.flush()

    async def _insert(self, db: AsyncSession, owner_id: int, issue: Issue) -> None:
        entry = QueueEntry(user_id=owner_id, issue_id=issue.id, position=0.0, is_pinned=False)
        db.add(entry)
        await db.flush()
        await self._place_by_default(db, entry, issue)

    async def _place_by_default(self, db: AsyncSession, entry: QueueEntry, issue: Issue) -> None:
        """Put ``entry`` in the rest group directly above the first item that
        ranks lower by the default rule (FR-39)."""
        rows = [
            (e, i) for e, i in await self._active(db, entry.user_id)
            if not e.is_pinned and e.id != entry.id
        ]
        rest = [_item(e, i) for e, i in rows]
        index = queue_order.insertion_index(_item(entry, issue), rest)
        await self._set_position(db, entry, index)

    async def _set_position(self, db: AsyncSession, entry: QueueEntry, index: int) -> None:
        """Place ``entry`` at ``index`` of its own group (as ``entry.is_pinned``
        says), counted without it; renumber the group when the gap is too narrow."""
        for _ in range(2):
            active, dormant = await self._group_positions(db, entry)
            position = queue_order.position_at(active, index, dormant=dormant)
            if position is not None:
                break
            await self._renumber(db, entry.user_id, pinned=entry.is_pinned, exclude=entry.id)
        entry.position = position
        db.add(entry)
        await db.flush()

    async def _renumber(
        self, db: AsyncSession, owner_id: int, *, pinned: bool, exclude: int,
    ) -> None:
        """Evenly respace one group, keeping its order. The rest group includes
        dormant entries, so a return still lands where it was relative to them."""
        q = select(QueueEntry).where(
            QueueEntry.user_id == owner_id, QueueEntry.is_pinned.is_(pinned),
            QueueEntry.id != exclude,
        )
        if pinned:
            q = q.where(QueueEntry.left_at.is_(None))
        q = q.order_by(QueueEntry.position, QueueEntry.issue_id)
        entries = (await db.execute(q)).scalars().all()
        for entry, position in zip(entries, queue_order.renumbered(len(entries)), strict=True):
            entry.position = position
            db.add(entry)
        await db.flush()

    async def _group_positions(
        self, db: AsyncSession, entry: QueueEntry,
    ) -> tuple[list[float], list[float]]:
        """``(active, dormant)`` positions of ``entry``'s group, ascending,
        without ``entry`` itself. Only the rest group has dormant entries."""
        rows = (await db.execute(
            select(QueueEntry.position, QueueEntry.left_at).where(
                QueueEntry.user_id == entry.user_id,
                QueueEntry.is_pinned.is_(entry.is_pinned),
                QueueEntry.id != entry.id,
            ).order_by(QueueEntry.position, QueueEntry.issue_id)
        )).all()
        active = [p for p, left in rows if left is None]
        dormant = [p for p, left in rows if left is not None]
        return active, dormant

    @staticmethod
    def _clear_pin(entry: QueueEntry) -> None:
        entry.is_pinned = False
        entry.pin_locked = False
        entry.pinned_by_id = None
        entry.pinned_at = None

    # ── Reads ─────────────────────────────────────────────────────────────────

    async def _active(self, db: AsyncSession, owner_id: int) -> list[tuple[QueueEntry, Issue]]:
        """The owner's queue in order — pinned, then rest — dormant entries excluded."""
        rows = (await db.execute(
            select(QueueEntry, Issue)
            .join(Issue, Issue.id == QueueEntry.issue_id)
            .where(
                QueueEntry.user_id == owner_id,
                QueueEntry.left_at.is_(None),
                Issue.deleted_at.is_(None),
            )
            .options(*card_load_options(), selectinload(QueueEntry.pinned_by))
            .order_by(QueueEntry.is_pinned.desc(), QueueEntry.position, QueueEntry.issue_id)
        )).all()
        return [(e, i) for e, i in rows]

    async def queue(self, db: AsyncSession, owner: User) -> list[tuple[QueueEntry, Issue]]:
        return await self._active(db, owner.id)

    async def board(
        self, db: AsyncSession, owner: User, *, done_from: datetime, done_to: datetime | None,
    ) -> list[tuple[str, list[Issue], dict[int, QueueEntry]]]:
        """One group per board status. Open columns follow queue order (AC-41);
        Done lists the owner's items completed in ``[done_from, done_to]``, newest first."""
        active = await self._active(db, owner.id)
        entries = {i.id: e for e, i in active}
        done_q = select(Issue).where(
            Issue.assignee_id == owner.id,
            Issue.deleted_at.is_(None),
            Issue.status == IssueStatus.done.value,
            Issue.completed_at >= done_from,
        )
        if done_to is not None:
            done_q = done_q.where(Issue.completed_at <= done_to)
        done = (await db.execute(
            done_q.options(*card_load_options())
            .order_by(Issue.completed_at.desc(), Issue.id.desc())
        )).scalars().all()
        columns = []
        for s in BOARD_STATUSES:
            if s == IssueStatus.done:
                columns.append((s.value, list(done), {}))
            else:
                in_column = [i for _, i in active if _value(i.status) == s.value]
                columns.append((s.value, in_column, entries))
        return columns

    async def history(
        self, db: AsyncSession, owner: User, *, page: int, size: int,
        since: datetime | None = None, until: datetime | None = None,
        actor_id: int | None = None, not_owner: bool = False,
        action: str | None = None, item_type: str | None = None, q: str | None = None,
    ) -> tuple[list[QueueHistory], int, dict]:
        """The owner's queue history, newest first, filtered — plus facet
        counts over the date range and search only, so every filter option can
        say how many changes it would show."""
        base = (
            select(QueueHistory)
            .outerjoin(Issue, Issue.id == QueueHistory.issue_id)
            .where(QueueHistory.user_id == owner.id)
        )
        if since is not None:
            base = base.where(QueueHistory.created_at >= since)
        if until is not None:
            base = base.where(QueueHistory.created_at <= until)
        if q and q.strip():
            needle = q.strip().lstrip("#")
            clauses = [Issue.title.ilike(f"%{needle}%")]
            key = needle.upper().replace("BUG-", "").replace("TASK-", "")
            if key.isdigit():
                clauses += [Issue.issue_number == int(key), Issue.id == int(key)]
            base = base.where(or_(*clauses))

        facets = await self._history_facets(db, owner, base)

        filtered = base
        if actor_id is not None:
            filtered = filtered.where(QueueHistory.actor_id == actor_id)
        if not_owner:
            filtered = filtered.where(QueueHistory.actor_id != owner.id)
        if action:
            filtered = filtered.where(QueueHistory.action == action)
        if item_type:
            filtered = filtered.where(Issue.type == item_type)

        total = (await db.execute(
            select(func.count()).select_from(filtered.subquery())
        )).scalar_one()
        rows = (await db.execute(
            filtered.options(selectinload(QueueHistory.actor), selectinload(QueueHistory.issue))
            .order_by(QueueHistory.created_at.desc(), QueueHistory.id.desc())
            .offset((page - 1) * size).limit(size)
        )).scalars().all()
        return list(rows), total, facets

    @staticmethod
    async def _history_facets(db: AsyncSession, owner: User, base) -> dict:
        sub = base.with_only_columns(
            QueueHistory.actor_id, QueueHistory.action, Issue.type,
        ).subquery()
        rows = (await db.execute(select(sub.c.actor_id, sub.c.action, sub.c.type))).all()
        actions = {a.value: 0 for a in QueueAction}
        types = {"bug": 0, "task": 0}
        by_actor: dict[int, int] = {}
        for actor_id, action, item_type in rows:
            actions[_value(action)] = actions.get(_value(action), 0) + 1
            if item_type is not None:
                types[_value(item_type)] = types.get(_value(item_type), 0) + 1
            if actor_id is not None:
                by_actor[actor_id] = by_actor.get(actor_id, 0) + 1
        users = {}
        if by_actor:
            users = {u.id: u for u in (await db.execute(
                select(User).where(User.id.in_(by_actor))
            )).scalars().all()}
        return {
            "total": len(rows),
            "not_owner": sum(n for a, n in by_actor.items() if a != owner.id),
            "actions": actions,
            "types": types,
            "actors": [
                {"actor": UserSummary.model_validate(users[a]), "count": n}
                for a, n in sorted(by_actor.items(), key=lambda kv: (-kv[1], kv[0]))
                if a in users
            ],
        }

    # ── Human actions (recorded in queue history) ─────────────────────────────

    async def move(
        self, db: AsyncSession, owner: User, actor: User, issue_id: int,
        *, before_id: int | None, after_id: int | None,
    ) -> None:
        """Drag within a group (FR-38). Refuses a cross-group move (``queue_group_boundary``)."""
        await _lock_queue(db, owner.id)
        active = await self._active(db, owner.id)
        items = [_item(e, i) for e, i in active]
        try:
            index = queue_order.move_index(items, issue_id, before_id=before_id, after_id=after_id)
        except QueueRuleError as err:
            raise _refused(err) from err
        entry, issue = next((e, i) for e, i in active if i.id == issue_id)
        old_index = queue_order.absolute_index(items, issue_id)
        await self._set_position(db, entry, index)
        new_index = await self._index_of(db, owner.id, issue_id)
        if new_index != old_index:
            await self._record(db, owner, actor, QueueAction.reorder, issue, old_index, new_index)

    async def pin(self, db: AsyncSession, owner: User, actor: User, issue_id: int) -> None:
        """Pin to the end of the pin group (FR-40). A CTO or Admin pinning
        someone else's queue locks the pin (BR-41)."""
        await _lock_queue(db, owner.id)
        entry, issue = await self._entry_or_404(db, owner.id, issue_id)
        if entry.is_pinned:
            return
        pins_used = sum(1 for e, _ in await self._active(db, owner.id) if e.is_pinned)
        if pins_used >= PIN_LIMIT:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                f"This queue already has {PIN_LIMIT} pins — the limit. Unpin one first.",
                "pin_limit_reached",
            )
        old_index = await self._index_of(db, owner.id, issue_id)
        entry.is_pinned = True
        entry.pinned_by_id = actor.id
        entry.pin_locked = actor.id != owner.id
        entry.pinned_at = datetime.now(tz=UTC)
        await self._set_position(db, entry, pins_used)
        new_index = await self._index_of(db, owner.id, issue_id)
        await self._record(db, owner, actor, QueueAction.pin, issue, old_index, new_index)

    async def unpin(self, db: AsyncSession, owner: User, actor: User, issue_id: int) -> None:
        """Unpin and re-place by the default rule. The owner can't remove a locked pin (BR-41)."""
        await _lock_queue(db, owner.id)
        entry, issue = await self._entry_or_404(db, owner.id, issue_id)
        if not entry.is_pinned:
            raise DomainError(status.HTTP_409_CONFLICT, "That item isn't pinned.", "not_pinned")
        if entry.pin_locked and actor.id == owner.id:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "A CTO or Admin pinned this — only a CTO or Admin can unpin it.",
                "pin_locked",
            )
        old_index = await self._index_of(db, owner.id, issue_id)
        self._clear_pin(entry)
        await db.flush()
        await self._place_by_default(db, entry, issue)
        new_index = await self._index_of(db, owner.id, issue_id)
        await self._record(db, owner, actor, QueueAction.unpin, issue, old_index, new_index)

    async def _entry_or_404(self, db: AsyncSession, owner_id: int, issue_id: int):
        for entry, issue in await self._active(db, owner_id):
            if issue.id == issue_id:
                return entry, issue
        raise DomainError(
            status.HTTP_404_NOT_FOUND, "That item isn't in this queue.", "not_in_queue",
        )

    async def _index_of(self, db: AsyncSession, owner_id: int, issue_id: int) -> int | None:
        items = [_item(e, i) for e, i in await self._active(db, owner_id)]
        return queue_order.absolute_index(items, issue_id)

    async def _record(
        self, db: AsyncSession, owner: User, actor: User, action: QueueAction,
        issue: Issue, old_index: int | None, new_index: int | None,
    ) -> None:
        """Append to the owner's queue history, and tell the owner when someone
        else changed their queue (BR-43)."""
        db.add(QueueHistory(
            user_id=owner.id, actor_id=actor.id, action=action.value, issue_id=issue.id,
            old_index=old_index, new_index=new_index,
        ))
        await db.flush()
        if actor.id != owner.id:
            from app.services.inbox_service import InboxFanOutService

            await InboxFanOutService().fan_out(
                db=db, trigger=InboxEventType.queue_changed, issue=issue, actor=actor,
                meta={"action": action.value, "old_index": old_index, "new_index": new_index},
            )

    # ── Scheduled: due-date notices (§13) ─────────────────────────────────────

    async def notify_due_items(self, db: AsyncSession, now: datetime) -> dict[str, list[int]]:
        """One ``due_soon`` notice when an open assigned item's due date is within
        24 hours, and one ``overdue`` once it has passed — each at most once,
        per ``*_notified_at``. The caller commits."""
        from app.services.inbox_service import InboxFanOutService

        today = now.astimezone(UTC).date()
        base = (
            Issue.deleted_at.is_(None),
            Issue.assignee_id.is_not(None),
            Issue.due_date.is_not(None),
            Issue.status.in_([s.value for s in QUEUE_STATUSES]),
        )
        # A due date is a day: it is "passed" once that day is over, and "within
        # 24 hours" once its end is less than a day away.
        overdue = (await db.execute(
            select(Issue).where(*base, Issue.due_date < today, Issue.overdue_notified_at.is_(None))
        )).scalars().all()
        soon = (await db.execute(
            select(Issue).where(
                *base, Issue.due_date == today, Issue.due_soon_notified_at.is_(None),
            )
        )).scalars().all()

        fan_out = InboxFanOutService()
        for issue in soon:
            issue.due_soon_notified_at = now
            db.add(issue)
            await fan_out.fan_out(
                db=db, trigger=InboxEventType.due_soon, issue=issue, actor=None,
                meta={"due_date": issue.due_date.isoformat()},
            )
        for issue in overdue:
            issue.overdue_notified_at = now
            if issue.due_soon_notified_at is None:
                # Passed without a "due soon" first — don't send it late.
                issue.due_soon_notified_at = now
            db.add(issue)
            await fan_out.fan_out(
                db=db, trigger=InboxEventType.overdue, issue=issue, actor=None,
                meta={"due_date": issue.due_date.isoformat()},
            )
        await db.flush()
        return {"due_soon": [i.id for i in soon], "overdue": [i.id for i in overdue]}

    # ── Team overview (slice 11) ──────────────────────────────────────────────

    async def workload(
        self, db: AsyncSession, now: datetime, *,
        role: str | None = None, project_id: int | None = None,
    ) -> list[WorkloadRow]:
        """Every active assignable user's In progress items, next three and counts.

        A fixed number of queries whatever the team size (never one per user):
        the people, their active entries (with each item's status), then the
        cards for just the items shown. People come in name order — the view
        never ranks anyone by load. ``project_id`` keeps people with open
        queued work in that project.
        """
        active = (QueueEntry.left_at.is_(None), Issue.deleted_at.is_(None))
        people_q = select(User).where(
            User.is_active.is_(True), User.role.in_(sorted(ASSIGNABLE_ROLES)),
        )
        if role is not None:
            people_q = people_q.where(User.role == role)
        if project_id is not None:
            people_q = people_q.where(
                select(QueueEntry.id)
                .join(Issue, Issue.id == QueueEntry.issue_id)
                .where(QueueEntry.user_id == User.id, Issue.project_id == project_id, *active)
                .exists()
            )
        people = (await db.execute(
            people_q.order_by(func.lower(User.name), User.id)
        )).scalars().all()
        if not people:
            return []

        rows = (await db.execute(
            select(QueueEntry, Issue.status)
            .join(Issue, Issue.id == QueueEntry.issue_id)
            .where(QueueEntry.user_id.in_([u.id for u in people]), *active)
            .order_by(
                QueueEntry.user_id, QueueEntry.is_pinned.desc(),
                QueueEntry.position, QueueEntry.issue_id,
            )
        )).all()

        loads = {u.id: _Workload() for u in people}
        shown: dict[int, QueueEntry] = {}
        for entry, item_status in rows:
            load = loads[entry.user_id]
            load.open += 1
            load.pinned += int(entry.is_pinned)
            if _value(item_status) == IssueStatus.in_progress.value:
                load.in_progress.append(entry.issue_id)
            elif len(load.next) < WORKLOAD_NEXT:
                load.next.append(entry.issue_id)
            else:
                continue
            shown[entry.issue_id] = entry

        issues = (await db.execute(
            select(Issue).where(Issue.id.in_(list(shown))).options(*card_load_options())
        )).scalars().all() if shown else []
        cards = {c.id: c for c in await build_cards(db, list(issues), now, shown)}

        return [
            WorkloadRow(
                user=UserSummary.model_validate(u),
                in_progress=[cards[i] for i in loads[u.id].in_progress],
                next=[cards[i] for i in loads[u.id].next],
                counts=WorkloadCounts(open=loads[u.id].open, pinned=loads[u.id].pinned),
            )
            for u in people
        ]

    # ── Owners ────────────────────────────────────────────────────────────────

    @staticmethod
    def has_queue(user: User) -> bool:
        return _value(user.role) != UserRole.support.value


queue_service = QueueService()
