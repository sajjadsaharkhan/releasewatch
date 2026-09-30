"""ReleaseService — the release lifecycle, ship, cancel, activity, and the overdue notice.

Slice 09 (docs/phase-2/09-releases-and-stream.md, PRD FR-46–FR-54, BR-47,
BR-48, BR-55–BR-57, §13).

- Every release status change asks ``app/release_lifecycle.py``; Released is
  reached only through ``ship``.
- ``ship`` is the one place ship effects are written: the release becomes
  Released, every open item goes to the backlog (Default, To do, assignee
  kept, cycles deleted), and ``release_shipped`` is fanned out. ``cancel``
  moves open items the same way.
- ``release_events`` (the Activity tab) are written only here;
  ``record_item_move`` is called by every path that changes an item's container.
- Progress and Overdue are computed on read, never stored.
"""

from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import release_lifecycle as lifecycle
from app.core.errors import DomainError
from app.db.models.inbox_item import InboxEventType
from app.db.models.issue import Issue, IssueStatus, issue_key
from app.db.models.project import Project
from app.db.models.release import Release, ReleaseKind, ReleaseStatus
from app.db.models.release_event import ReleaseEvent, ReleaseEventType
from app.db.models.user import User, UserRole
from app.policy import Action, allows
from app.services.authz import actor_of, project_target

#: Every status an item counts under on the release page (triage statuses included).
COUNT_STATUSES: tuple[str, ...] = tuple(s.value for s in IssueStatus)
#: The not-Done statuses the ship notice lists (FR-53).
SHIP_NOTICE_STATUSES: tuple[str, ...] = tuple(
    s.value for s in (
        IssueStatus.todo, IssueStatus.rejected, IssueStatus.in_progress,
        IssueStatus.to_review, IssueStatus.in_review, IssueStatus.blocked,
    )
)
#: Board column order (FR-47, FR-51) — Blocked sits before Done on container boards.
#: Rejected is its own key; the frontend shows it on top of the To do column (09a).
BOARD_COLUMNS: tuple[str, ...] = tuple(
    s.value for s in (
        IssueStatus.todo, IssueStatus.rejected, IssueStatus.in_progress,
        IssueStatus.to_review, IssueStatus.in_review, IssueStatus.blocked, IssueStatus.done,
    )
)
#: The Stream's Done column shows this many days unless a range is given (FR-47).
STREAM_DONE_DAYS = 7
#: Open = neither Done nor Cancelled — what ship and cancel move to the backlog.
_CLOSED_ITEM_STATUSES = (IssueStatus.done.value, IssueStatus.cancelled.value)

#: Fields whose change is a ``dates_changed`` event; the rest are ``edited``.
_DATE_FIELDS = ("code_freeze_date", "target_date")


def _value(v):
    return getattr(v, "value", v)


def _jsonable(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


def is_overdue(release: Release, now: datetime) -> bool:
    """BR-48: a target ship date that has passed (by the server's calendar) on a
    release that isn't Released or Cancelled. Never on the Stream or undated."""
    if release.is_stream or release.target_date is None or release.is_closed:
        return False
    return release.target_date.astimezone().date() < now.astimezone().date()


def progress(counts: dict[str, int]) -> float | None:
    """BR-47: Done ÷ non-cancelled items; ``None`` with no non-cancelled item."""
    denominator = sum(counts.values()) - counts.get("cancelled", 0)
    if denominator <= 0:
        return None
    return counts.get("done", 0) / denominator


def _refuse(check: lifecycle.Check) -> None:
    if not check.ok:
        raise DomainError(status.HTTP_409_CONFLICT, check.detail, check.code, check.allowed)


def _ensure_editable(release: Release) -> None:
    """The Stream is immutable (FR-46); a Released or Cancelled release is read-only (FR-54)."""
    if release.is_stream:
        from app.services.container_service import stream_immutable

        raise stream_immutable()
    if release.is_closed:
        raise DomainError(
            status.HTTP_409_CONFLICT,
            f"A {lifecycle.label(release.status)} release is final and read-only.",
            "release_final",
        )


class ReleaseService:

    # ── Reads ────────────────────────────────────────────────────────────────

    @staticmethod
    async def counts(db: AsyncSession, release_id: int) -> dict[str, int]:
        """Items in the release by status (every status, zeros included)."""
        rows = await db.execute(
            select(Issue.status, func.count(Issue.id))
            .where(Issue.release_id == release_id, Issue.deleted_at.is_(None))
            .group_by(Issue.status)
        )
        out = {s: 0 for s in COUNT_STATUSES}
        for st, n in rows.all():
            out[_value(st)] = n
        return out

    @staticmethod
    async def has_done_items(db: AsyncSession, release_id: int) -> bool:
        return (await db.execute(
            select(func.count(Issue.id)).where(
                Issue.release_id == release_id,
                Issue.deleted_at.is_(None),
                Issue.status == IssueStatus.done.value,
            )
        )).scalar_one() > 0

    async def permissions(
        self, db: AsyncSession, release: Release, user: User,
    ) -> tuple[list[str], list[str]]:
        """``(allowed_transitions, allowed_actions)`` for ``user`` — the UI renders
        these and never re-derives them."""
        if release.is_stream or release.is_closed:
            return [], []
        project = await db.get(Project, release.project_id)
        actor, target = actor_of(user), project_target(project)
        actions: list[str] = []
        transitions: list[str] = []
        if allows(actor, Action.manage_releases, target):
            actions.append(Action.manage_releases.value)
            transitions = lifecycle.allowed_targets(
                release.kind, release.status,
                has_done_items=await self.has_done_items(db, release.id),
            )
        if allows(actor, Action.ship_release, target) and lifecycle.can_ship(
            release.kind, release.status,
        ).ok:
            actions.append(Action.ship_release.value)
        if allows(actor, Action.go_nogo, target):
            actions.append(Action.go_nogo.value)
        return transitions, actions

    # ── Create and edit (FR-49) ──────────────────────────────────────────────

    async def create(self, db: AsyncSession, project: Project, data: dict, actor: User) -> Release:
        release = Release(
            project_id=project.id,
            version=data["version"],
            description=data.get("description"),
            target_date=data.get("target_date"),
            code_freeze_date=data.get("code_freeze_date"),
            staging_url=data.get("staging_url"),
            created_by_id=actor.id,
        )
        db.add(release)
        await db.flush()
        # The Activity tab starts here: created, in Planning.
        self._event(db, release, actor, ReleaseEventType.created, {
            "version": release.version, "status": _value(release.status),
        })
        await db.flush()
        return release

    async def edit(self, db: AsyncSession, release: Release, changes: dict, actor: User) -> Release:
        """PATCH: fields, and a ``status`` routed through the lifecycle."""
        _ensure_editable(release)
        to_status = changes.pop("status", None)

        dated, edited = {}, {}
        for field, value in changes.items():
            old = getattr(release, field)
            if old == value:
                continue
            (dated if field in _DATE_FIELDS else edited)[field] = {
                "from": _jsonable(old), "to": _jsonable(value),
            }
            setattr(release, field, value)
        if "target_date" in dated:
            # A new date gets its own overdue notice (§13).
            release.overdue_notified_at = None
        if dated:
            self._event(db, release, actor, ReleaseEventType.dates_changed, {"changes": dated})
        if edited:
            self._event(db, release, actor, ReleaseEventType.edited, {"changes": edited})
        db.add(release)
        await db.flush()

        if to_status is not None and _value(to_status) != _value(release.status):
            await self.change_status(db, release, _value(to_status), actor)
        return release

    # ── Lifecycle (FR-50) ────────────────────────────────────────────────────

    async def change_status(
        self, db: AsyncSession, release: Release, to: str, actor: User,
        *, now: datetime | None = None,
    ) -> Release:
        """A manual lifecycle move; Cancelled goes through ``cancel``."""
        if _value(to) == ReleaseStatus.cancelled.value:
            return await self.cancel(db, release, actor, now=now)
        _refuse(lifecycle.can_change(release.kind, release.status, to))
        await self._set_status(db, release, to, actor)
        return release

    async def cancel(
        self, db: AsyncSession, release: Release, actor: User, *, now: datetime | None = None,
    ) -> Release:
        """BR-55: refused with a Done item; open items move to the backlog like a ship."""
        _refuse(lifecycle.can_change(
            release.kind, release.status, ReleaseStatus.cancelled.value,
            has_done_items=await self.has_done_items(db, release.id),
        ))
        await self._move_open_items_to_backlog(db, release, actor, reason="cancel")
        await self._set_status(db, release, ReleaseStatus.cancelled.value, actor)
        return release

    async def _set_status(self, db: AsyncSession, release: Release, to: str, actor: User) -> None:
        old = _value(release.status)
        release.status = to
        db.add(release)
        self._event(db, release, actor, ReleaseEventType.status_changed, {"from": old, "to": to})
        await db.flush()

    # ── Go / no-go (FR-52) ───────────────────────────────────────────────────

    async def go_nogo(
        self, db: AsyncSession, release: Release, decision: str, note: str | None, actor: User,
        *, now: datetime | None = None,
    ) -> Release:
        _ensure_editable(release)
        release.go_nogo_status = _value(decision)
        release.go_nogo_note = note
        release.go_nogo_by_id = actor.id
        release.go_nogo_at = now or datetime.now(tz=UTC)
        db.add(release)
        self._event(db, release, actor, ReleaseEventType.go_nogo, {
            "decision": _value(decision), "note": note,
        })
        await db.flush()
        return release

    # ── Ship (FR-53, BR-56) ──────────────────────────────────────────────────

    async def ship_preview(self, db: AsyncSession, release: Release) -> dict:
        _refuse(lifecycle.can_ship(release.kind, release.status))
        counts = await self.counts(db, release.id)
        not_done = {s: counts.get(s, 0) for s in SHIP_NOTICE_STATUSES}
        # Items still in triage move too — they count toward the total.
        total = sum(
            n for s, n in counts.items() if s not in _CLOSED_ITEM_STATUSES
        )
        return {
            "go_nogo": {
                "status": _value(release.go_nogo_status),
                "note": release.go_nogo_note,
                "by_id": release.go_nogo_by_id,
                "at": release.go_nogo_at,
            },
            "not_done": not_done,
            "total_not_done": total,
            "done": counts.get("done", 0),
        }

    async def ship(
        self, db: AsyncSession, release: Release, actor: User, *, now: datetime | None = None,
    ) -> Release:
        """One transaction (the caller commits): Released + ``released_at``, a
        ``shipped`` event, open items to the backlog, ``release_shipped`` fan-out."""
        _refuse(lifecycle.can_ship(release.kind, release.status))
        now = now or datetime.now(tz=UTC)
        counts = await self.counts(db, release.id)

        assignee_ids = set((await db.execute(
            select(Issue.assignee_id).where(
                Issue.release_id == release.id,
                Issue.deleted_at.is_(None),
                Issue.assignee_id.is_not(None),
                Issue.status != IssueStatus.cancelled.value,
            )
        )).scalars().all())

        release.status = ReleaseStatus.released.value
        release.released_at = now
        db.add(release)
        # One ``shipped`` event records the QA → Released move (no separate status_changed).
        moved = await self._move_open_items_to_backlog(db, release, actor, reason="ship")
        self._event(db, release, actor, ReleaseEventType.shipped, {
            "moved": len(moved),
            "not_done": {
                s: n for s, n in counts.items() if s not in _CLOSED_ITEM_STATUSES and n
            },
            "go_nogo": _value(release.go_nogo_status),
        })
        await db.flush()

        from app.services.inbox_service import inbox_service

        ctos = set((await db.execute(
            select(User.id).where(User.role == UserRole.cto, User.is_active.is_(True))
        )).scalars().all())
        roles = {uid: {"assignee"} for uid in assignee_ids}
        await inbox_service.fan_out_release(
            db, InboxEventType.release_shipped, release, actor, assignee_ids | ctos,
            meta={"version": release.version, "moved": len(moved)}, roles=roles,
        )
        return release

    # ── Delete ───────────────────────────────────────────────────────────────

    async def delete(self, db: AsyncSession, release: Release, *, now: datetime | None = None) -> None:
        """Soft-delete. Never the Stream (FR-46) or a Released release, which is
        read-only history (FR-54)."""
        if release.is_stream:
            from app.services.container_service import stream_immutable

            raise stream_immutable()
        if release.is_shipped:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "A Released release is read-only and can't be deleted.",
                "release_final",
            )
        release.deleted_at = now or datetime.now(tz=UTC)
        db.add(release)
        await db.flush()

    # ── Board (FR-47, FR-51) ─────────────────────────────────────────────────

    @staticmethod
    def done_window(
        release: Release, now: datetime, done_from: datetime | None, done_to: datetime | None,
    ) -> tuple[datetime | None, datetime | None]:
        """The Done range to apply: the caller's, or — on the Stream with none
        given — the last ``STREAM_DONE_DAYS`` days (AC-63). A Release is unbounded."""
        if release.is_stream and done_from is None and done_to is None:
            done_from = now - timedelta(days=STREAM_DONE_DAYS)
        return done_from, done_to

    async def _container_items(
        self,
        db: AsyncSession,
        release: Release,
        user: User,
        *,
        statuses: tuple[str, ...] | None,
        done_from: datetime | None,
        done_to: datetime | None,
    ) -> list[Issue]:
        """Visible items in the container. Done items are bounded by the window;
        every other status is always included. ``statuses`` limits the set (the board)."""
        from sqlalchemy.orm import selectinload

        from app.services.authz import visibility_clause

        done = IssueStatus.done.value
        done_bounds = []
        if done_from is not None:
            done_bounds.append(Issue.completed_at >= done_from)
        if done_to is not None:
            done_bounds.append(Issue.completed_at <= done_to)
        not_done = Issue.status != done if statuses is None else Issue.status.in_(
            [s for s in statuses if s != done]
        )
        included = or_(not_done, and_(Issue.status == done, *done_bounds))
        return list((await db.execute(
            select(Issue)
            .options(
                selectinload(Issue.assignee), selectinload(Issue.reporter),
                selectinload(Issue.release), selectinload(Issue.project),
            )
            .where(
                Issue.release_id == release.id, Issue.deleted_at.is_(None),
                visibility_clause(user), included,
            )
            .order_by(Issue.completed_at.desc().nulls_last(), Issue.created_at.desc(), Issue.id.desc())
        )).scalars().all())

    async def board(
        self,
        db: AsyncSession,
        release: Release,
        user: User,
        *,
        now: datetime,
        done_from: datetime | None = None,
        done_to: datetime | None = None,
    ) -> tuple[list[tuple[str, list[Issue]]], datetime | None, datetime | None]:
        """One group per ``BOARD_COLUMNS`` status, in board order — Rejected is its
        own group; the frontend draws it inside To do (09a). Only Done is bounded
        (``done_window``)."""
        done_from, done_to = self.done_window(release, now, done_from, done_to)
        rows = await self._container_items(
            db, release, user, statuses=BOARD_COLUMNS, done_from=done_from, done_to=done_to,
        )
        columns = [
            (col, [i for i in rows if _value(i.status) == col]) for col in BOARD_COLUMNS
        ]
        return columns, done_from, done_to

    async def items(
        self,
        db: AsyncSession,
        release: Release,
        user: User,
        *,
        now: datetime,
        done_from: datetime | None = None,
        done_to: datetime | None = None,
    ) -> tuple[list[Issue], datetime | None, datetime | None]:
        """The Items tab: every item in the container, with Done bounded the same
        way as the board's Done column, so both tabs share one range."""
        done_from, done_to = self.done_window(release, now, done_from, done_to)
        rows = await self._container_items(
            db, release, user, statuses=None, done_from=done_from, done_to=done_to,
        )
        return rows, done_from, done_to

    async def _move_open_items_to_backlog(
        self, db: AsyncSession, release: Release, actor: User, *, reason: str,
    ) -> list[int]:
        """Every item that is neither Done nor Cancelled → To do, in the backlog
        with category Default; assignee kept; cycles deleted (BR-62) by
        ``IssueService.update``. No per-item notifications — the ship notice covers it."""
        from app.services.backlog_category_service import backlog_category_service
        from app.services.issue_service import issue_service

        items = (await db.execute(
            select(Issue).where(
                Issue.release_id == release.id,
                Issue.deleted_at.is_(None),
                Issue.status.notin_(_CLOSED_ITEM_STATUSES),
            ).order_by(Issue.id)
        )).scalars().all()
        if not items:
            return []
        default = await backlog_category_service.default_for(db, release.project_id)
        moved: list[int] = []
        for issue in items:
            if _value(issue.status) != IssueStatus.todo.value:
                await issue_service.transition(
                    db, issue, IssueStatus.todo, actor, reason=reason, notify=False,
                )
            await issue_service.update(
                db, issue.id,
                {"release_id": None, "backlog_category_id": default.id},
                actor, notify=False, move_reason=reason,
            )
            moved.append(issue.id)
        return moved

    # ── Activity (FR-51) ─────────────────────────────────────────────────────

    @staticmethod
    def _event(
        db: AsyncSession, release: Release, actor: User | None, kind: ReleaseEventType, meta: dict,
    ) -> None:
        db.add(ReleaseEvent(
            release_id=release.id,
            actor_id=actor.id if actor is not None else None,
            event_type=kind.value,
            meta=meta,
            created_at=datetime.now(tz=UTC),
        ))

    async def record_item_move(
        self,
        db: AsyncSession,
        issue: Issue,
        old_release_id: int | None,
        new_release_id: int | None,
        actor: User | None,
        *,
        reason: str | None = None,
    ) -> None:
        """``item_removed`` / ``item_added`` on the Releases an item left or joined.
        The Stream has no Activity tab, so it records nothing."""
        if old_release_id == new_release_id:
            return
        meta = {
            "issue_id": issue.id,
            "issue_number": issue.issue_number,
            "key": issue_key(issue.type, issue.issue_number),
            "title": issue.title,
        }
        if reason:
            meta["reason"] = reason
        for rid, kind in (
            (old_release_id, ReleaseEventType.item_removed),
            (new_release_id, ReleaseEventType.item_added),
        ):
            if rid is None:
                continue
            release = await db.get(Release, rid)
            if release is None or release.is_stream:
                continue
            self._event(db, release, actor, kind, meta)

    @staticmethod
    async def activity(db: AsyncSession, release_id: int) -> list[ReleaseEvent]:
        from sqlalchemy.orm import selectinload

        return list((await db.execute(
            select(ReleaseEvent)
            .options(selectinload(ReleaseEvent.actor))
            .where(ReleaseEvent.release_id == release_id)
            # Oldest first: the Activity tab reads as the release's story, top to bottom.
            .order_by(ReleaseEvent.created_at.asc(), ReleaseEvent.id.asc())
        )).scalars().all())

    # ── Overdue notice (§13) ─────────────────────────────────────────────────

    async def notify_overdue(self, db: AsyncSession, now: datetime) -> list[int]:
        """Tell active CTOs, once per target date, about each release that has
        passed it. Returns the ids notified. The caller commits."""
        candidates = (await db.execute(
            select(Release).where(
                Release.deleted_at.is_(None),
                Release.kind == ReleaseKind.release.value,
                Release.target_date.is_not(None),
                Release.overdue_notified_at.is_(None),
                Release.status.notin_([s.value for s in (
                    ReleaseStatus.released, ReleaseStatus.cancelled,
                )]),
            )
        )).scalars().all()
        overdue = [r for r in candidates if is_overdue(r, now)]
        if not overdue:
            return []

        from app.services.inbox_service import inbox_service

        ctos = set((await db.execute(
            select(User.id).where(User.role == UserRole.cto, User.is_active.is_(True))
        )).scalars().all())
        for release in overdue:
            release.overdue_notified_at = now
            db.add(release)
            await inbox_service.fan_out_release(
                db, InboxEventType.release_overdue, release, None, ctos,
                meta={
                    "version": release.version,
                    "target_date": release.target_date.isoformat(),
                },
            )
        await db.flush()
        return [r.id for r in overdue]


release_service = ReleaseService()

