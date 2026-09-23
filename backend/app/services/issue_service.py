"""IssueService — domain logic for creating and advancing issues.

All public methods are ``async`` and accept an ``AsyncSession`` as their first
argument so they can be composed inside a single DB transaction when needed.

``transition()`` is the only method that writes ``issue.status`` — every
other status-changing method (``triage``, ``needs_clarification``,
``mark_fixed``, ``verify_fix``, ``reopen``, ``regress``) ends by calling it.
See docs/phase-2/02-unified-status-model.md and ``app/workflow.py``.
"""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.models.inbox_item import InboxEventType
from app.db.models.issue import Issue, IssueSource, IssueStatus, IssueType, Priority, issue_type_value
from app.db.models.issue_timeline import TimelineEventType
from app.db.models.project import ProjectKind
from app.db.models.user import User
from app.policy import is_assignable
from app.schemas.issue import IssueCreate
from app.workflow import Workflow


async def ensure_assignable(db: AsyncSession, assignee_id: int | None) -> None:
    """BR-32 — refuse (422 ``not_assignable``) giving work to a Support or inactive user."""
    if assignee_id is None:
        return
    user = await db.get(User, int(assignee_id))
    if user is None or not user.is_active or not is_assignable(user.role):
        raise DomainError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "That user can't be assigned work.",
            "not_assignable",
        )


class IssueService:
    """Encapsulates all state transitions and business rules for ``Issue`` rows."""

    # ── Creation ──────────────────────────────────────────────────────────────

    async def create(
        self,
        db: AsyncSession,
        data: IssueCreate,
        current_user: User,
        *,
        source: IssueSource = IssueSource.internal,
        filed_meta: dict | None = None,
    ) -> Issue:
        """File a new issue (bug or task) against a project, optionally a release.

        Automatically assigns the next ``issue_number`` and appends a
        ``filed`` timeline event. Bugs start in ``new`` (BR-11 — every bug
        passes triage). Tasks start in ``todo`` and skip triage (BR-12).

        ``source`` and ``filed_meta`` are set only by ``SupportService`` (slice
        05) — ``/issues`` always files ``internal`` items. ``filed_meta`` is
        merged into the ``filed`` event's meta (the template submission's
        forensic copy).
        """
        from app.db.models.project import Project
        from app.db.models.release import Release
        from app.services.inbox_service import InboxFanOutService
        from app.services.timeline_service import TimelineService

        project_result = await db.execute(select(Project).where(Project.id == data.project_id))
        project = project_result.scalar_one_or_none()
        if project is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

        await ensure_assignable(db, data.assignee_id)

        release = None
        if data.release_id is not None:
            project_kind = getattr(project.kind, "value", project.kind)
            if project_kind != ProjectKind.product.value:
                raise DomainError(
                    status.HTTP_409_CONFLICT,
                    "Only Product projects accept a release.",
                    "releases_not_allowed",
                )
            release_result = await db.execute(select(Release).where(Release.id == data.release_id))
            release = release_result.scalar_one_or_none()
            if release is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")
            if release.project_id != data.project_id:
                raise DomainError(
                    status.HTTP_409_CONFLICT,
                    "That release belongs to a different project.",
                    "release_project_mismatch",
                )

        now = datetime.now(tz=UTC)
        initial_status = IssueStatus.todo if data.type == IssueType.task else IssueStatus.new

        reproduction_steps_json = [
            {
                "step_order": step.step_order,
                "description": step.description,
                "expected_result": step.expected_result,
                "actual_result": step.actual_result,
            }
            for step in data.reproduction_steps
        ]

        issue = Issue(
            project_id=data.project_id,
            release_id=data.release_id,
            type=data.type,
            source=source,
            title=data.title,
            description=data.description,
            priority=data.priority,
            due_date=data.due_date,
            labels=data.labels,
            is_release_blocker=data.is_release_blocker,
            environment_browser=data.environment_browser,
            environment_os=data.environment_os,
            environment_build_hash=data.environment_build_hash,
            environment_staging_url=data.environment_staging_url,
            environment_name=data.environment_name,
            curl_command=data.curl_command,
            reporter_id=current_user.id,
            assignee_id=data.assignee_id,
            status=initial_status,
            created_at=now,
            filed_at=now,
            reproduction_steps=reproduction_steps_json or [],
        )
        db.add(issue)
        await db.flush()

        from app.db.models.issue_cycle import IssueCycle
        db.add(IssueCycle(issue_id=issue.id, cycle_number=1, cycle_start_at=now))
        await db.flush()

        timeline_svc = TimelineService()
        await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=current_user.id,
            event_type=TimelineEventType.filed,
            body=None,
            meta={"priority": data.priority.value if data.priority else None, **(filed_meta or {})},
            is_internal=False,
        )

        if data.pending_attachments:
            from app.db.models.issue_attachment import IssueAttachment

            for pending in data.pending_attachments:
                db.add(IssueAttachment(
                    issue_id=issue.id,
                    uploaded_by_id=current_user.id,
                    file_name=pending.filename,
                    s3_key=pending.s3_key,
                    mime_type=pending.mime_type,
                    file_size_bytes=pending.file_size_bytes,
                    attachment_type=pending.attachment_type,
                ))

        await db.flush()

        # Fan-out: notify triage leads of new issue
        await InboxFanOutService().fan_out(
            db=db,
            trigger=InboxEventType.filed,
            issue=issue,
            actor=current_user,
        )

        # Fan-out: notify triage leads + CTOs if blocker
        if data.is_release_blocker:
            await InboxFanOutService().fan_out(
                db=db,
                trigger=InboxEventType.blocker_filed,
                issue=issue,
                actor=current_user,
            )

        return issue

    # ── Transition — the only code that writes issue.status ─────────────────────

    async def transition(
        self,
        db: AsyncSession,
        issue: Issue,
        to: IssueStatus | str,
        actor: User,
        *,
        reason: str | None = None,
        comment: str | None = None,
        cancel_reason: str | None = None,
        _internal_context: dict | None = None,
    ) -> Issue:
        """Move ``issue`` to status ``to``, or raise ``DomainError`` (409).

        Asks ``Workflow`` first. On success: sets the status-support columns
        (``started_at``, ``completed_at``, ``cancelled_at``,
        ``blocked_from_status``, ``review_requested_by_id``), keeps
        ``IssueCycle`` bookkeeping (``fixed_at`` on entering ``in_review``,
        ``verified_at`` on reaching ``done`` from ``in_review``), writes one
        ``status_changed`` timeline event, and fans out ``status_changed``.
        """
        from app.db.models.release import Release
        from app.services.inbox_service import InboxFanOutService
        from app.services.timeline_service import TimelineService

        from_status = IssueStatus(issue.status) if isinstance(issue.status, str) else issue.status
        to_status = IssueStatus(to) if isinstance(to, str) else to

        has_release = issue.release_id is not None
        release_shipped = False
        if has_release:
            release_result = await db.execute(select(Release).where(Release.id == issue.release_id))
            release = release_result.scalar_one_or_none()
            if release is not None:
                release_shipped = release.is_shipped

        context = {
            "actor_id": actor.id,
            "review_requested_by_id": issue.review_requested_by_id,
            "blocked_from_status": issue.blocked_from_status,
            "has_release": has_release,
            "release_shipped": release_shipped,
            "reason": reason,
            "cancel_reason": cancel_reason,
            **(_internal_context or {}),
        }

        item_type = issue_type_value(issue.type)
        check = Workflow.can_transition(item_type, from_status.value, to_status.value, context)
        if not check.ok:
            raise DomainError(status.HTTP_409_CONFLICT, check.detail, check.code, check.allowed)

        now = datetime.now(tz=UTC)

        from app.db.models.issue_cycle import IssueCycle
        active_cycle_result = await db.execute(
            select(IssueCycle)
            .where(IssueCycle.issue_id == issue.id)
            .order_by(IssueCycle.cycle_number.desc())
            .limit(1)
        )
        active_cycle = active_cycle_result.scalar_one_or_none()

        issue.status = to_status

        if to_status == IssueStatus.in_progress:
            if issue.started_at is None:
                issue.started_at = now
            if from_status in (IssueStatus.done, IssueStatus.in_review):
                issue.verified_at = None
                issue.completed_at = None
            if from_status == IssueStatus.in_review:
                issue.review_requested_by_id = None

        elif to_status == IssueStatus.in_review:
            issue.review_requested_by_id = actor.id
            issue.fixed_at = now
            ref = issue.triaged_at or issue.filed_at
            if ref:
                issue.time_to_fix_h = round((now - ref).total_seconds() / 3600, 2)
            if active_cycle and not active_cycle.fixed_at:
                active_cycle.fixed_at = now
                cycle_ref = active_cycle.triaged_at or active_cycle.cycle_start_at
                active_cycle.time_to_fix_h = round((now - cycle_ref).total_seconds() / 3600, 2)
                db.add(active_cycle)

        elif to_status == IssueStatus.done:
            issue.completed_at = now
            if from_status == IssueStatus.in_review:
                issue.verified_at = now
                if issue.fixed_at:
                    issue.time_to_verify_h = round((now - issue.fixed_at).total_seconds() / 3600, 2)
                if active_cycle and not active_cycle.verified_at:
                    active_cycle.verified_at = now
                    if active_cycle.fixed_at:
                        active_cycle.time_to_verify_h = round(
                            (now - active_cycle.fixed_at).total_seconds() / 3600, 2
                        )
                    db.add(active_cycle)

        elif to_status == IssueStatus.blocked:
            issue.blocked_from_status = from_status.value

        elif to_status == IssueStatus.cancelled:
            issue.cancel_reason = cancel_reason
            issue.cancelled_at = now

        if from_status == IssueStatus.blocked and to_status != IssueStatus.blocked:
            issue.blocked_from_status = None

        # Movement is unrestricted, so an item can leave done or cancelled for
        # any status — it's no longer completed or cancelled once it does.
        if from_status == IssueStatus.done and to_status != IssueStatus.done:
            issue.completed_at = None
            issue.verified_at = None
        if from_status == IssueStatus.cancelled and to_status != IssueStatus.cancelled:
            issue.cancel_reason = None

        db.add(issue)
        await db.flush()

        timeline_svc = TimelineService()
        event = await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=actor.id,
            event_type=TimelineEventType.status_changed,
            body=comment,
            meta={
                "from": from_status.value, "to": to_status.value,
                "reason": cancel_reason or reason,
            },
            is_internal=False,
        )

        await InboxFanOutService().fan_out(
            db=db, trigger=InboxEventType.status_changed, issue=issue, actor=actor,
            timeline_event=event,
            meta={"from": from_status.value, "to": to_status.value},
        )

        return issue

    # ── Regression action ─────────────────────────────────────────────────────

    async def regress(
        self,
        db: AsyncSession,
        issue_id: int,
        current_user: User,
    ) -> Issue:
        """Flag a regression: transitions the bug back to ``in_progress``.

        Records a ``RegressionHistory`` row when the bug has a release
        (``regression_history.release_id`` is NOT NULL until slice 06) —
        skipped silently otherwise so this stays callable from any status.
        """
        from app.db.models.release import Release
        from app.services.regression_service import regression_service

        issue = await self._get_issue_or_404(db, issue_id)

        release = None
        if issue.release_id is not None:
            release_result = await db.execute(select(Release).where(Release.id == issue.release_id))
            release = release_result.scalar_one_or_none()

        if release is not None:
            await regression_service.record_regression(db, issue, release, current_user)

        return await self.transition(
            db, issue, to=IssueStatus.in_progress, actor=current_user,
            _internal_context={"via_regression": True},
        )

    # ── Reopen — maps to the regression action ────────────────────────────────

    async def reopen(
        self,
        db: AsyncSession,
        issue_id: int,
        current_user: User,
    ) -> Issue:
        """Reopen a Done bug. Maps to the regression action; Done is otherwise final."""
        issue = await self._get_issue_or_404(db, issue_id)
        if getattr(issue.status, "value", issue.status) != IssueStatus.done.value:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "Only a Done bug can be reopened.",
                "done_is_final",
            )
        try:
            return await self.regress(db, issue_id, current_user)
        except DomainError as exc:
            if exc.code in ("no_release", "release_shipped"):
                raise DomainError(
                    status.HTTP_409_CONFLICT,
                    "Only a Done bug in an unshipped release can be reopened.",
                    "done_is_final",
                ) from exc
            raise

    # ── Triage ────────────────────────────────────────────────────────────────

    async def triage(
        self,
        db: AsyncSession,
        issue_id: int,
        assignee_id: int,
        priority: Priority,
        current_user: User,
        labels: list[str] | None = None,
        is_release_blocker: bool | None = None,
    ) -> Issue:
        """Triage an issue: assign it and set its priority (required, BR-16).

        Transitions status ``new -> todo`` (the Phase 1 triage endpoint maps
        to the new "accept" outcome in this slice; full triage outcomes land
        in slice 06).
        """
        from app.services.inbox_service import InboxFanOutService
        from app.services.timeline_service import TimelineService

        issue = await self._get_issue_or_404(db, issue_id)
        if getattr(issue.status, "value", issue.status) != IssueStatus.new.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot triage an issue in status '{issue.status}'",
            )

        now = datetime.now(tz=UTC)
        prev_priority = getattr(issue.priority, "value", issue.priority)
        prev_assignee = issue.assignee_id

        await ensure_assignable(db, assignee_id)
        issue.assignee_id = assignee_id
        issue.priority = priority
        issue.triaged_at = now
        if labels is not None:
            issue.labels = labels
        if is_release_blocker is not None:
            issue.is_release_blocker = is_release_blocker
        if issue.filed_at:
            delta = now - issue.filed_at
            issue.time_to_triage_h = round(delta.total_seconds() / 3600, 2)

        from app.db.models.issue_cycle import IssueCycle
        active_cycle_result = await db.execute(
            select(IssueCycle)
            .where(IssueCycle.issue_id == issue_id)
            .order_by(IssueCycle.cycle_number.desc())
            .limit(1)
        )
        active_cycle = active_cycle_result.scalar_one_or_none()
        if active_cycle:
            if active_cycle.assignee_id != assignee_id:
                active_cycle.assignee_id = assignee_id
            if not active_cycle.triaged_at:
                active_cycle.triaged_at = now
                active_cycle.time_to_triage_h = round(
                    (now - active_cycle.cycle_start_at).total_seconds() / 3600, 2
                )
            db.add(active_cycle)

        timeline_svc = TimelineService()
        if prev_priority != priority.value:
            await timeline_svc.create_event(
                db=db,
                issue_id=issue.id,
                actor_id=current_user.id,
                event_type=TimelineEventType.priority_changed,
                body=None,
                meta={"from": prev_priority, "to": priority.value},
                is_internal=False,
            )
        await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=current_user.id,
            event_type=TimelineEventType.assigned,
            body=None,
            meta={
                "assignee_id": str(assignee_id),
                "prev_assignee_id": str(prev_assignee) if prev_assignee else None,
            },
            is_internal=False,
        )

        db.add(issue)
        await db.flush()

        issue = await self.transition(
            db, issue, to=IssueStatus.todo, actor=current_user,
            _internal_context={"via_triage": True},
        )

        # Fan-out: assignee gets notified (transition() already fanned out status_changed).
        await InboxFanOutService().fan_out(
            db=db, trigger=InboxEventType.assigned, issue=issue, actor=current_user,
        )

        return issue

    # ── Needs Clarification ───────────────────────────────────────────────────

    async def needs_clarification(
        self,
        db: AsyncSession,
        issue_id: int,
        current_user: User,
        message: str | None = None,
    ) -> Issue:
        """Move a new issue to Needs info pending reporter clarification.

        Transitions status ``new -> needs_info``, reassigns to the reporter,
        and posts a ``needs_clarification`` timeline event (with optional
        message).
        """
        from app.services.inbox_service import InboxFanOutService
        from app.services.timeline_service import TimelineService

        issue = await self._get_issue_or_404(db, issue_id)
        if getattr(issue.status, "value", issue.status) != IssueStatus.new.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot request clarification on an issue in status '{issue.status}'",
            )

        prev_assignee_id = issue.assignee_id
        # The ball goes back to the reporter — unless they can't hold work (BR-32:
        # a Support reporter is never assigned); then the assignee stays put.
        reporter = await db.get(User, issue.reporter_id) if issue.reporter_id else None
        if reporter is not None and is_assignable(reporter.role):
            issue.assignee_id = issue.reporter_id
        db.add(issue)
        await db.flush()

        timeline_svc = TimelineService()
        timeline_event = await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=current_user.id,
            event_type=TimelineEventType.needs_clarification,
            body=message or None,
            meta={"prev_assignee_id": str(prev_assignee_id) if prev_assignee_id else None},
            is_internal=False,
        )

        meta = {"body_snippet": message} if message else None
        await InboxFanOutService().fan_out(
            db=db,
            trigger=InboxEventType.needs_clarification,
            issue=issue,
            actor=current_user,
            timeline_event=timeline_event,
            meta=meta,
        )

        return await self.transition(
            db, issue, to=IssueStatus.needs_info, actor=current_user,
            _internal_context={"via_needs_info": True},
        )

    # ── Fix ───────────────────────────────────────────────────────────────────

    async def mark_fixed(
        self,
        db: AsyncSession,
        issue_id: int,
        mr_url: str | None,
        current_user: User,
    ) -> Issue:
        """Mark an issue as fixed (developer submits MR): ``todo | in_progress -> in_review``."""
        issue = await self._get_issue_or_404(db, issue_id)
        return await self.transition(
            db, issue, to=IssueStatus.in_review, actor=current_user, comment=mr_url,
        )

    # ── Verify ────────────────────────────────────────────────────────────────

    async def verify_fix(
        self,
        db: AsyncSession,
        issue_id: int,
        outcome: str,  # "pass" | "fail" | "partial"
        current_user: User,
    ) -> Issue:
        """QA verifies a developer's fix.

        - ``pass`` -> transitions to ``done`` (blocked with ``self_verification``
          if the caller moved it to review themselves — AC-27)
        - ``fail`` -> transitions back to ``in_progress``
        - ``partial`` -> stays ``in_review``, just logs a comment
        """
        issue = await self._get_issue_or_404(db, issue_id)
        if getattr(issue.status, "value", issue.status) != IssueStatus.in_review.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Can only verify issues in 'in_review' status.",
            )

        if outcome == "pass":
            return await self.transition(db, issue, to=IssueStatus.done, actor=current_user)
        if outcome == "fail":
            return await self.transition(db, issue, to=IssueStatus.in_progress, actor=current_user)

        # partial — no status change, just a note on the timeline.
        from app.services.timeline_service import TimelineService

        timeline_svc = TimelineService()
        await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=current_user.id,
            event_type=TimelineEventType.status_changed,
            body=None,
            meta={"outcome": outcome},
            is_internal=False,
        )
        return issue

    # ── Duplicate linking ─────────────────────────────────────────────────────

    async def link_duplicate(
        self,
        db: AsyncSession,
        issue_id: int,
        parent_id: int,
        current_user: User,
    ) -> Issue:
        """Mark ``issue_id`` as a duplicate of ``parent_id``.

        Sets ``parent_issue_id`` and cancels the issue with reason
        ``duplicate``. Bypasses Workflow deliberately: full duplicate-merge
        semantics (BR-49/50) land in slice 06; this keeps the Phase 1 action
        working from any status in the meantime.
        """
        from app.services.timeline_service import TimelineService

        issue = await self._get_issue_or_404(db, issue_id)
        parent = await self._get_issue_or_404(db, parent_id)

        if issue_id == parent_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An issue cannot be a duplicate of itself.",
            )

        issue.parent_issue_id = parent_id
        issue.status = IssueStatus.cancelled
        issue.cancel_reason = "duplicate"
        issue.cancelled_at = datetime.now(tz=UTC)

        timeline_svc = TimelineService()
        await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=current_user.id,
            event_type=TimelineEventType.duplicate_linked,
            body=None,
            meta={"parent_issue_id": str(parent_id), "parent_number": parent.issue_number},
            is_internal=False,
        )

        db.add(issue)
        await db.flush()
        return issue

    # ── Generic update with field diffing ─────────────────────────────────────

    async def update(
        self,
        db: AsyncSession,
        issue_id: int,
        payload: dict,
        actor: User,
    ) -> Issue:
        """Apply a partial update to an issue, emitting a timeline event per changed field.

        A ``status`` field routes through ``transition()`` — see D8
        (docs/phase-2/00-README.md).

        Parameters
        ----------
        db:
            Active async session.
        issue_id:
            UUID of the issue to update.
        payload:
            Dict of only the fields to change (``exclude_unset=True`` in the route).
        actor:
            The authenticated user making the change.

        Returns
        -------
        Issue
            Updated issue row (flushed, not committed).
        """
        from app.db.models.release import Release
        from app.services.inbox_service import InboxFanOutService
        from app.services.timeline_service import TimelineService

        # Lock the row to prevent concurrent diff races
        result = await db.execute(
            select(Issue).where(Issue.id == issue_id).with_for_update()
        )
        issue = result.scalar_one_or_none()
        if issue is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

        if "type" in payload:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "type is immutable once an item is created (BR-07).",
                "type_immutable",
            )

        timeline_svc = TimelineService()
        inbox_svc = InboxFanOutService()
        events_to_emit: list[tuple[TimelineEventType, dict]] = []
        inbox_triggers: list[tuple[InboxEventType, dict | None]] = []

        # ── Title ─────────────────────────────────────────────────────────────
        if "title" in payload and payload["title"] != issue.title:
            events_to_emit.append((
                TimelineEventType.title_changed,
                {"from": issue.title, "to": payload["title"]},
            ))
            issue.title = payload["title"]

        # ── Description ───────────────────────────────────────────────────────
        if "description" in payload and payload["description"] != issue.description:
            events_to_emit.append((TimelineEventType.description_changed, {}))
            issue.description = payload["description"]

        # ── Priority ──────────────────────────────────────────────────────────
        if "priority" in payload:
            new_priority = payload["priority"]
            old_val = getattr(issue.priority, 'value', issue.priority)
            new_val = getattr(new_priority, 'value', new_priority)
            if old_val != new_val:
                events_to_emit.append((
                    TimelineEventType.priority_changed,
                    {"from": old_val, "to": new_val},
                ))
                inbox_triggers.append((
                    InboxEventType.priority_changed, {"from": old_val, "to": new_val},
                ))
                issue.priority = new_priority

        # ── Environment name ──────────────────────────────────────────────────
        if "environment_name" in payload and payload["environment_name"] != issue.environment_name:
            _old_env = issue.environment_name
            _new_env = payload["environment_name"]
            events_to_emit.append((
                TimelineEventType.environment_changed,
                {"from": _old_env, "to": _new_env},
            ))
            inbox_triggers.append((
                InboxEventType.environment_changed, {"from": _old_env, "to": _new_env},
            ))
            issue.environment_name = _new_env

        # ── Release blocker ───────────────────────────────────────────────────
        if (
            "is_release_blocker" in payload
            and payload["is_release_blocker"] != issue.is_release_blocker
        ):
            if payload["is_release_blocker"]:
                events_to_emit.append((TimelineEventType.blocker_flagged, {}))
                inbox_triggers.append((InboxEventType.blocker_filed, None))
            else:
                events_to_emit.append((TimelineEventType.blocker_cleared, {}))
                inbox_triggers.append((InboxEventType.blocker_cleared, None))
            issue.is_release_blocker = payload["is_release_blocker"]

        # ── Assignee ──────────────────────────────────────────────────────────
        if "assignee_id" in payload:
            new_assignee = payload["assignee_id"]
            new_assignee_str = str(new_assignee) if new_assignee else None
            old_assignee_str = str(issue.assignee_id) if issue.assignee_id else None
            if new_assignee_str != old_assignee_str:
                await ensure_assignable(db, new_assignee)
                events_to_emit.append((
                    TimelineEventType.assigned,
                    {"assignee_id": new_assignee_str, "prev_assignee_id": old_assignee_str},
                ))
                inbox_triggers.append((InboxEventType.assigned, None))
                issue.assignee_id = new_assignee

                from app.db.models.issue_cycle import IssueCycle as _IssueCycle
                _cycle_result = await db.execute(
                    select(_IssueCycle)
                    .where(_IssueCycle.issue_id == issue_id)
                    .order_by(_IssueCycle.cycle_number.desc())
                    .limit(1)
                )
                _active_cycle = _cycle_result.scalar_one_or_none()
                if _active_cycle:
                    _active_cycle.assignee_id = new_assignee
                    db.add(_active_cycle)

        # ── Labels ────────────────────────────────────────────────────────────
        if "labels" in payload:
            old_labels = set(issue.labels or [])
            new_labels = set(payload["labels"] or [])
            for added in sorted(new_labels - old_labels):
                events_to_emit.append((TimelineEventType.label_added, {"label_name": added}))
            for removed in sorted(old_labels - new_labels):
                events_to_emit.append((TimelineEventType.label_removed, {"label_name": removed}))
            issue.labels = list(new_labels)

        # ── Reproduction steps ────────────────────────────────────────────────
        if (
            "reproduction_steps" in payload
            and payload["reproduction_steps"] != issue.reproduction_steps
        ):
            events_to_emit.append((TimelineEventType.steps_changed, {}))
            issue.reproduction_steps = payload["reproduction_steps"]

        # ── Release ───────────────────────────────────────────────────────────
        if "release_id" in payload:
            new_release_id = payload["release_id"]
            if new_release_id != issue.release_id:
                # Resolve version strings for the diff meta
                from_version = None
                to_version = None
                if issue.release_id:
                    from_rel = await db.execute(
                        select(Release).where(Release.id == issue.release_id)
                    )
                    from_rel_obj = from_rel.scalar_one_or_none()
                    if from_rel_obj:
                        from_version = from_rel_obj.version
                if new_release_id:
                    to_rel = await db.execute(select(Release).where(Release.id == new_release_id))
                    to_rel_obj = to_rel.scalar_one_or_none()
                    if to_rel_obj:
                        to_version = to_rel_obj.version
                events_to_emit.append((
                    TimelineEventType.release_changed,
                    {"from_version": from_version, "to_version": to_version},
                ))
                inbox_triggers.append((
                    InboxEventType.release_changed,
                    {"from": from_version or "—", "to": to_version or "—"},
                ))
                issue.release_id = new_release_id

        # ── Project ───────────────────────────────────────────────────────────
        if "project_id" in payload:
            new_project_id = payload["project_id"]
            if new_project_id != issue.project_id:
                from app.db.models.project import Project
                from_name = None
                to_name = None
                if issue.project_id:
                    from_proj = await db.execute(
                        select(Project).where(Project.id == issue.project_id)
                    )
                    from_proj_obj = from_proj.scalar_one_or_none()
                    if from_proj_obj:
                        from_name = from_proj_obj.name
                if new_project_id:
                    to_proj = await db.execute(select(Project).where(Project.id == new_project_id))
                    to_proj_obj = to_proj.scalar_one_or_none()
                    if to_proj_obj:
                        to_name = to_proj_obj.name
                events_to_emit.append((
                    TimelineEventType.project_changed,
                    {"from_name": from_name, "to_name": to_name},
                ))
                inbox_triggers.append((
                    InboxEventType.project_changed,
                    {"from": from_name or "—", "to": to_name or "—"},
                ))
                issue.project_id = new_project_id

        # ── Passthrough fields with no timeline event ─────────────────────────
        for field in ("environment_browser", "environment_os", "environment_build_hash",
                      "environment_staging_url", "curl_command", "due_date"):
            if field in payload:
                setattr(issue, field, payload[field])

        db.add(issue)
        await db.flush()

        # Emit timeline events
        for event_type, meta in events_to_emit:
            await timeline_svc.create_event(
                db=db,
                issue_id=issue.id,
                actor_id=actor.id,
                event_type=event_type,
                body=None,
                meta=meta,
                is_internal=False,
            )

        # Fan-out inbox notifications
        for trigger, trigger_meta in inbox_triggers:
            await inbox_svc.fan_out(
                db=db, trigger=trigger, issue=issue, actor=actor, meta=trigger_meta,
            )

        # ── Status (routes through transition(), D8) ───────────────────────────
        if "status" in payload:
            new_status = payload["status"]
            old_status_val = getattr(issue.status, 'value', issue.status)
            new_status_val = getattr(new_status, 'value', new_status)
            if old_status_val != new_status_val:
                issue = await self.transition(
                    db, issue, to=new_status, actor=actor,
                    cancel_reason=payload.get("cancel_reason"),
                )

        return issue

    # ── Lookup ────────────────────────────────────────────────────────────────

    async def get(self, db: AsyncSession, issue_id: int) -> Issue:
        """Fetch an issue by ID or raise 404. Public — safe for callers outside the service."""
        return await self._get_issue_or_404(db, issue_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    async def _get_issue_or_404(db: AsyncSession, issue_id: int) -> Issue:
        """Fetch an issue by ID or raise 404."""
        result = await db.execute(select(Issue).where(Issue.id == issue_id))
        issue = result.scalar_one_or_none()
        if issue is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
        return issue


# Module-level singleton
issue_service = IssueService()
