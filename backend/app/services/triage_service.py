"""TriageService — the four triage outcomes, moving projects, and the Needs info auto-return.

Slice 06 (docs/phase-2/06-triage-outcomes.md, FR-17–20, BR-16–21, BR-49).
A triager (any tech role — Policy ``triage``) applies one outcome to a New or
Needs info bug:

- **Accept** — priority required; assignee and container optional. Omitting
  ``release_id`` keeps the bug's container (none for a support report);
  sending ``null`` puts it in the backlog, the Stream's id in the Stream
  (08a). → ``todo``.
- **Needs info** — a public comment saying what's missing. → ``needs_info``.
- **Duplicate** — a merge into an original (bug or task) in the same project
  (``MergeService.merge_into``). → ``cancelled`` (reason ``duplicate``).
- **Reject** — user error, expected behavior, or cannot reproduce. → ``cancelled``.

Every outcome writes one ``triaged`` timeline event carrying its inputs.
"""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.models.inbox_item import InboxEventType
from app.db.models.issue import (
    TRIAGE_STATUSES,
    Issue,
    IssueCancelReason,
    IssueStatus,
    issue_key,
)
from app.db.models.issue_subscriber import IssueSubscriber, SubscriptionReason
from app.db.models.issue_timeline import TimelineEventType
from app.db.models.project import Project
from app.db.models.release import Release
from app.db.models.user import User, UserRole
from app.schemas.issue import (
    AcceptOutcome,
    DuplicateOutcome,
    NeedsInfoOutcome,
    RejectOutcome,
    TriageRequest,
)
from app.services import container_service as containers
from app.services.inbox_service import InboxFanOutService
from app.services.issue_service import ensure_assignable, issue_service
from app.db.models.backlog_category import BacklogCategory
from app.services.backlog_category_service import backlog_category_service, snapshot
from app.services.cycle_service import cycle_service
from app.services.merge_service import lock_original, merge_service
from app.services.subscriber_service import subscribe
from app.services.timeline_service import TimelineService
from app.tasks import search_index

_TRIAGE_VALUES = {s.value for s in TRIAGE_STATUSES}


def _status(issue: Issue) -> str:
    return getattr(issue.status, "value", issue.status)


def _key(issue: Issue) -> str:
    return issue_key(issue.type, issue.issue_number)


def _snippet(body: str | None) -> str | None:
    if not body:
        return None
    return body[:200] + "…" if len(body) > 200 else body


def _quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def merge_comment(duplicate: Issue, note: str | None = None) -> str:
    """The public comment a Duplicate outcome adds to the original (FR-18 v2.1, AC-49):
    where it came from, the triager's own note when they wrote one, then the
    duplicate's title and description as a quote."""
    parts = [f"**{duplicate.title}**"]
    if duplicate.description:
        parts += ["", duplicate.description]
    key = _key(duplicate)
    # A relative link, so it works on whatever host serves the app.
    head = f"Merged from [{key}](/issue/{key.lower()})\n\n"
    if note and note.strip():
        head += f"{note.strip()}\n\n"
    return head + _quote("\n".join(parts))


class TriageService:

    async def apply(
        self, db: AsyncSession, issue: Issue, payload: TriageRequest, actor: User,
    ) -> Issue:
        if _status(issue) not in _TRIAGE_VALUES:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "Only New and Needs info bugs can be triaged.",
                "not_in_triage",
            )
        outcome = payload.root
        if isinstance(outcome, AcceptOutcome):
            return await self._accept(db, issue, outcome, actor)
        if isinstance(outcome, NeedsInfoOutcome):
            return await self._needs_info(db, issue, outcome, actor)
        if isinstance(outcome, DuplicateOutcome):
            return await self._duplicate(db, issue, outcome, actor)
        return await self._reject(db, issue, outcome, actor)

    # ── Accept ────────────────────────────────────────────────────────────────

    async def _accept(
        self, db: AsyncSession, issue: Issue, outcome: AcceptOutcome, actor: User,
    ) -> Issue:
        timeline = TimelineService()
        now = datetime.now(tz=UTC)

        # An optional category — checked before anything is written.
        category = None
        if outcome.backlog_category_id is not None:
            category = await backlog_category_service.resolve(
                db, issue.project_id, outcome.backlog_category_id,
            )

        await ensure_assignable(db, outcome.assignee_id)
        if "release_id" in outcome.model_fields_set and outcome.release_id != issue.release_id:
            await self._set_release(db, issue, outcome.release_id, actor)

        prev_priority = getattr(issue.priority, "value", issue.priority)
        if prev_priority != outcome.priority.value:
            await timeline.create_event(
                db=db, issue_id=issue.id, actor_id=actor.id,
                event_type=TimelineEventType.priority_changed, body=None,
                meta={"from": prev_priority, "to": outcome.priority.value},
            )
        issue.priority = outcome.priority

        assignee_changed = (
            outcome.assignee_id is not None and outcome.assignee_id != issue.assignee_id
        )
        if assignee_changed:
            await timeline.create_event(
                db=db, issue_id=issue.id, actor_id=actor.id,
                event_type=TimelineEventType.assigned, body=None,
                meta={
                    "assignee_id": str(outcome.assignee_id),
                    "prev_assignee_id": str(issue.assignee_id) if issue.assignee_id else None,
                },
            )
            issue.assignee_id = outcome.assignee_id

        if category is not None and category.id != issue.backlog_category_id:
            previous = await db.get(BacklogCategory, issue.backlog_category_id)
            await timeline.create_event(
                db=db, issue_id=issue.id, actor_id=actor.id,
                event_type=TimelineEventType.backlog_category_changed, body=None,
                meta={
                    "from": snapshot(previous) if previous else None, "to": snapshot(category),
                },
            )
            issue.backlog_category_id = category.id

        issue.triaged_at = now
        if issue.filed_at:
            issue.time_to_triage_h = round((now - issue.filed_at).total_seconds() / 3600, 2)
        await cycle_service.on_assignee(db, issue)

        await timeline.create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.triaged, body=None,
            meta={
                "outcome": "accept",
                "priority": outcome.priority.value,
                "assignee_id": issue.assignee_id,
                "release_id": issue.release_id,
                **({"backlog_category_id": category.id} if category is not None else {}),
            },
        )
        db.add(issue)
        await db.flush()

        issue = await issue_service.transition(db, issue, to=IssueStatus.todo, actor=actor)
        if issue.assignee_id is not None:
            await InboxFanOutService().fan_out(
                db=db, trigger=InboxEventType.assigned, issue=issue, actor=actor,
            )
        return issue

    async def _set_release(
        self, db: AsyncSession, issue: Issue, release_id: int | None, actor: User,
    ) -> None:
        from_release = await db.get(Release, issue.release_id) if issue.release_id else None
        to_release = await containers.resolve(db, issue.project_id, release_id)
        await TimelineService().create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.release_changed, body=None,
            meta={
                "from_version": from_release.version if from_release else None,
                "to_version": to_release.version if to_release else None,
            },
        )
        old_release_id = issue.release_id
        issue.release_id = release_id
        db.add(issue)
        await cycle_service.after_container_change(db, issue, old_release_id, actor)
        from app.services.release_service import release_service

        await release_service.record_item_move(db, issue, old_release_id, release_id, actor)
        # BR-58: leaving a Release drops the blocker flag.
        if issue.is_release_blocker and (to_release is None or to_release.is_stream):
            issue.is_release_blocker = False
            await TimelineService().create_event(
                db=db, issue_id=issue.id, actor_id=actor.id,
                event_type=TimelineEventType.blocker_cleared, body=None,
                meta={"reason": "left_release"},
            )

    # ── Needs info ────────────────────────────────────────────────────────────

    async def _needs_info(
        self, db: AsyncSession, issue: Issue, outcome: NeedsInfoOutcome, actor: User,
    ) -> Issue:
        timeline = TimelineService()
        question = await timeline.create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.comment, body=outcome.comment,
            meta={"needs_info_question": True},
            is_internal=False,
        )
        await timeline.create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.triaged, body=None,
            meta={"outcome": "needs_info", "comment_id": question.id},
        )
        # Phase 1's notice to the reporter (kept for tech reporters, story 24);
        # fan_out drops a Support reporter, who gets support_needs_info instead.
        await InboxFanOutService().fan_out(
            db=db, trigger=InboxEventType.needs_clarification, issue=issue, actor=actor,
            timeline_event=question, meta={"body_snippet": _snippet(outcome.comment)},
        )
        if _status(issue) == IssueStatus.needs_info.value:
            # A follow-up question: no status move, but Support still hears it.
            await issue_service.notify_support(
                db, issue, IssueStatus.needs_info, actor, question=outcome.comment,
            )
            return issue
        return await issue_service.transition(
            db, issue, to=IssueStatus.needs_info, actor=actor, question=outcome.comment,
        )

    # ── Duplicate (merge) ─────────────────────────────────────────────────────

    async def _duplicate(
        self, db: AsyncSession, issue: Issue, outcome: DuplicateOutcome, actor: User,
    ) -> Issue:
        original = await lock_original(db, outcome.duplicate_of_id)
        if original is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
        if original.id == issue.id:
            raise DomainError(
                status.HTTP_409_CONFLICT, "A bug can't be a duplicate of itself.", "duplicate_of_self",
            )
        if original.project_id != issue.project_id:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "The original must be in the same project.",
                "duplicate_cross_project",
            )
        # The original may be a bug or a task (BR-20, 08a).
        if getattr(original.cancel_reason, "value", original.cancel_reason) == IssueCancelReason.duplicate.value:
            extra = {"suggested_id": original.parent_issue_id}
            parent = await db.get(Issue, original.parent_issue_id) if original.parent_issue_id else None
            if parent is not None:
                extra["suggested_key"] = _key(parent)
            raise DomainError(
                status.HTTP_409_CONFLICT,
                f"{_key(original)} is itself a duplicate.",
                "duplicate_of_duplicate",
                extra=extra,
            )

        timeline = TimelineService()
        if outcome.comment:
            await timeline.create_event(
                db=db, issue_id=issue.id, actor_id=actor.id,
                event_type=TimelineEventType.comment, body=outcome.comment, meta=None,
            )
        await timeline.create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.triaged, body=None,
            meta={
                "outcome": "duplicate",
                "duplicate_of_id": original.id,
                "duplicate_of_key": _key(original),
            },
        )
        issue.parent_issue_id = original.id
        db.add(issue)
        issue = await issue_service.transition(
            db, issue, to=IssueStatus.cancelled, actor=actor,
            cancel_reason=IssueCancelReason.duplicate.value,
        )

        # The duplicate's audience moves to the original (AC-20).
        subscribers = (await db.execute(
            select(IssueSubscriber.user_id).where(IssueSubscriber.issue_id == issue.id)
        )).scalars().all()
        for user_id in subscribers:
            await subscribe(db, original.id, user_id, SubscriptionReason.duplicate)

        await merge_service.merge_into(
            db, original,
            content_md=merge_comment(issue, outcome.comment),
            reporter_id=issue.reporter_id,
            merged_issue_id=issue.id,
            actor=actor,
            reason=SubscriptionReason.duplicate,
            comment_meta={"merged_from_id": issue.id, "merged_from_key": _key(issue)},
        )
        return issue

    # ── Reject ────────────────────────────────────────────────────────────────

    async def _reject(
        self, db: AsyncSession, issue: Issue, outcome: RejectOutcome, actor: User,
    ) -> Issue:
        # The comment is the whole explanation: no structured reason is stored.
        timeline = TimelineService()
        await timeline.create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.comment, body=outcome.comment, meta=None,
        )
        await timeline.create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.triaged, body=None,
            meta={"outcome": "reject"},
        )
        return await issue_service.transition(
            db, issue, to=IssueStatus.cancelled, actor=actor, question=outcome.comment,
        )

    # ── Move project (FR-20) ──────────────────────────────────────────────────

    async def move_project(
        self, db: AsyncSession, issue: Issue, project_id: int, actor: User,
        *, release_id: int | None = None, backlog_category_id: int | None = None,
    ) -> Issue:
        """Move an open item to another project and place it there (the Move…
        dialog). The item lands in the destination's Stream or an open Release
        (``release_id``), else its backlog — in ``backlog_category_id`` or the
        Default. Leaving a release drops the blocker flag (BR-58)."""
        if _status(issue) == IssueStatus.cancelled.value:
            raise DomainError(
                status.HTTP_409_CONFLICT, "A cancelled item can't be moved.", "item_closed",
            )
        if _status(issue) == IssueStatus.done.value:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "A Done item can't move to another project.",
                "done_item_immobile",
            )
        if release_id is not None and backlog_category_id is not None:
            raise DomainError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "A backlog category only applies to the backlog.",
                "category_needs_backlog",
                errors={"backlog_category_id": "Only for an item placed in the backlog."},
            )
        target = await db.get(Project, project_id)
        if target is None or target.archived_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        if target.id == issue.project_id:
            raise DomainError(
                status.HTTP_409_CONFLICT, "The item is already in that project.", "same_project",
            )
        container = await containers.resolve(db, target.id, release_id)
        category = await backlog_category_service.resolve(
            db, target.id, backlog_category_id if container is None else None,
        )

        source = await db.get(Project, issue.project_id)
        from_release = await db.get(Release, issue.release_id) if issue.release_id else None
        events: list[tuple[TimelineEventType, dict]] = [(
            TimelineEventType.project_changed,
            {"from_name": source.name if source else None, "to_name": target.name},
        )]
        if issue.release_id != release_id:
            events.append((
                TimelineEventType.release_changed,
                {
                    "from_version": from_release.version if from_release else None,
                    "to_version": container.version if container else None,
                },
            ))
        if issue.is_release_blocker and (container is None or container.is_stream):
            issue.is_release_blocker = False
            events.append((TimelineEventType.blocker_cleared, {"reason": "left_release"}))

        # Project, container and category move together — the composite FKs
        # check them as a set, and their rank belongs to the old backlog.
        issue.project_id = target.id
        issue.release_id = container.id if container else None
        issue.backlog_category_id = category.id
        issue.backlog_rank = None
        db.add(issue)
        await db.flush()
        search_index.enqueue(db, issue.id)
        search_index.enqueue_hints(db, issue.id)  # a New bug's candidates are per project (14)
        for event_type, meta in events:
            await TimelineService().create_event(
                db=db, issue_id=issue.id, actor_id=actor.id,
                event_type=event_type, body=None, meta=meta,
            )
        await InboxFanOutService().fan_out(
            db=db, trigger=InboxEventType.moved_into_project, issue=issue, actor=actor,
            meta={"from": source.name if source else "—", "to": target.name},
        )
        return issue

    # ── Needs info auto-return (FR-19, BR-19) ─────────────────────────────────

    async def on_comment(
        self, db: AsyncSession, issue: Issue, author: User, *, body: str | None, is_internal: bool,
    ) -> bool:
        """Send a Needs info item back to New when its reporter or any Support user
        answers publicly, and tell the triage lead. Returns whether it moved."""
        if _status(issue) != IssueStatus.needs_info.value or is_internal:
            return False
        is_support = getattr(author.role, "value", author.role) == UserRole.support.value
        if author.id != issue.reporter_id and not is_support:
            return False
        await issue_service.transition(db, issue, to=IssueStatus.new, actor=author)
        await InboxFanOutService().fan_out(
            db=db, trigger=InboxEventType.needs_info_replied, issue=issue, actor=author,
            meta={"body_snippet": _snippet(body)},
        )
        return True


triage_service = TriageService()
