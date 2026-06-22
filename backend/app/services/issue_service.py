"""IssueService — domain logic for creating and advancing issues.

All public methods are ``async`` and accept an ``AsyncSession`` as their first
argument so they can be composed inside a single DB transaction when needed.
"""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue import Issue, IssueSeverity, IssueStatus
from app.db.models.issue_timeline import TimelineEventType
from app.db.models.inbox_item import InboxEventType
from app.db.models.user import User
from app.schemas.issue import IssueCreate, IssueUpdate


class IssueService:
    """Encapsulates all state transitions and business rules for ``Issue`` rows."""

    # ── Creation ──────────────────────────────────────────────────────────────

    async def create(
        self,
        db: AsyncSession,
        data: IssueCreate,
        current_user: User,
    ) -> Issue:
        """File a new issue against a release.

        Automatically assigns the next ``issue_number`` within the project and
        appends a ``filed`` timeline event.
        """
        from app.db.models.release import Release
        from app.services.timeline_service import TimelineService
        from app.services.inbox_service import InboxFanOutService

        release_result = await db.execute(
            select(Release).where(Release.id == data.release_id)
        )
        release = release_result.scalar_one_or_none()
        if release is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")

        now = datetime.now(tz=timezone.utc)

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
            project_id=release.project_id,
            release_id=data.release_id,
            title=data.title,
            description=data.description,
            severity=data.severity,
            labels=data.labels,
            is_release_blocker=data.is_release_blocker,
            environment_browser=data.environment_browser,
            environment_os=data.environment_os,
            environment_build_hash=data.environment_build_hash,
            environment_staging_url=data.environment_staging_url,
            environment_name=data.environment_name,
            curl_command=data.curl_command,
            reporter_id=current_user.id,
            status=IssueStatus.new,
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
            meta={"severity": data.severity.value},
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

    # ── Triage ────────────────────────────────────────────────────────────────

    async def triage(
        self,
        db: AsyncSession,
        issue_id: int,
        assignee_id: int,
        severity: IssueSeverity,
        current_user: User,
        labels: list[str] | None = None,
        is_release_blocker: bool | None = None,
    ) -> Issue:
        """Triage an issue: assign it and set severity.

        Transitions status ``new → triaged``.
        """
        from app.services.timeline_service import TimelineService
        from app.services.inbox_service import InboxFanOutService

        issue = await self._get_issue_or_404(db, issue_id)
        if issue.status not in (IssueStatus.new,):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot triage an issue in status '{issue.status}'",
            )

        now = datetime.now(tz=timezone.utc)
        prev_severity = issue.severity
        prev_assignee = issue.assignee_id

        issue.assignee_id = assignee_id
        issue.severity = severity
        issue.status = IssueStatus.triaged
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
        if active_cycle and active_cycle.assignee_id != assignee_id:
            active_cycle.assignee_id = assignee_id
            db.add(active_cycle)

        timeline_svc = TimelineService()
        await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=current_user.id,
            event_type=TimelineEventType.status_changed,
            body=None,
            meta={"from": IssueStatus.new.value, "to": IssueStatus.triaged.value},
            is_internal=False,
        )
        if prev_severity != severity:
            await timeline_svc.create_event(
                db=db,
                issue_id=issue.id,
                actor_id=current_user.id,
                event_type=TimelineEventType.severity_changed,
                body=None,
                meta={"from": getattr(prev_severity, 'value', prev_severity), "to": getattr(severity, 'value', severity)},
                is_internal=False,
            )
        await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=current_user.id,
            event_type=TimelineEventType.assigned,
            body=None,
            meta={"assignee_id": str(assignee_id), "prev_assignee_id": str(prev_assignee) if prev_assignee else None},
            is_internal=False,
        )

        db.add(issue)
        await db.flush()

        # Fan-out: assignee gets notified
        await InboxFanOutService().fan_out(
            db=db, trigger=InboxEventType.assigned, issue=issue, actor=current_user,
        )
        # Fan-out: reporter + old assignee get status-changed notification
        await InboxFanOutService().fan_out(
            db=db, trigger=InboxEventType.status_changed, issue=issue, actor=current_user,
            meta={"from": IssueStatus.new.value, "to": IssueStatus.triaged.value},
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
        """Block an issue pending reporter clarification.

        Transitions status ``new → blocked``, reassigns to the reporter, and
        posts a ``needs_clarification`` timeline event (with optional message).
        """
        from app.services.timeline_service import TimelineService
        from app.services.inbox_service import InboxFanOutService

        issue = await self._get_issue_or_404(db, issue_id)
        if issue.status != IssueStatus.new:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot request clarification on an issue in status '{issue.status}'",
            )

        prev_assignee_id = issue.assignee_id
        issue.status = IssueStatus.blocked
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

        return issue

    # ── Fix ───────────────────────────────────────────────────────────────────

    async def mark_fixed(
        self,
        db: AsyncSession,
        issue_id: int,
        mr_url: str | None,
        current_user: User,
    ) -> Issue:
        """Mark an issue as fixed (developer submits MR).

        Transitions ``triaged | in_progress → fixed``.
        """
        from app.services.timeline_service import TimelineService
        from app.services.inbox_service import InboxFanOutService

        issue = await self._get_issue_or_404(db, issue_id)
        if issue.status not in (IssueStatus.triaged, IssueStatus.in_progress, IssueStatus.regression):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot mark fixed from status '{issue.status}'",
            )

        now = datetime.now(tz=timezone.utc)
        prev_status = issue.status
        issue.status = IssueStatus.fixed
        issue.fixed_at = now
        if issue.triaged_at:
            delta = now - issue.triaged_at
            issue.time_to_fix_h = round(delta.total_seconds() / 3600, 2)

        timeline_svc = TimelineService()
        await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=current_user.id,
            event_type=TimelineEventType.fixed,
            body=mr_url,
            meta={"from": getattr(prev_status, 'value', prev_status), "to": IssueStatus.fixed.value, "mr_url": mr_url},
            is_internal=False,
        )

        db.add(issue)
        await db.flush()

        # Fan-out: reporter + triage leads notified of fix
        await InboxFanOutService().fan_out(
            db=db, trigger=InboxEventType.fixed, issue=issue, actor=current_user,
        )

        return issue

    # ── Verify ────────────────────────────────────────────────────────────────

    async def verify_fix(
        self,
        db: AsyncSession,
        issue_id: int,
        outcome: str,  # "pass" | "fail" | "partial"
        current_user: User,
    ) -> Issue:
        """QA verifies a developer's fix.

        - ``pass`` → transitions to ``verified``
        - ``fail`` → transitions back to ``in_progress``
        - ``partial`` → stays ``fixed`` with a timeline comment
        """
        from app.services.timeline_service import TimelineService
        from app.services.inbox_service import InboxFanOutService

        issue = await self._get_issue_or_404(db, issue_id)
        if issue.status != IssueStatus.fixed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Can only verify issues in 'fixed' status.",
            )

        now = datetime.now(tz=timezone.utc)
        if outcome == "pass":
            issue.status = IssueStatus.verified
            issue.verified_at = now
            if issue.fixed_at:
                delta = now - issue.fixed_at
                issue.time_to_verify_h = round(delta.total_seconds() / 3600, 2)
            event_type = TimelineEventType.verified
        elif outcome == "fail":
            issue.status = IssueStatus.in_progress
            event_type = TimelineEventType.status_changed
        else:  # partial
            event_type = TimelineEventType.status_changed

        timeline_svc = TimelineService()
        await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=current_user.id,
            event_type=event_type,
            body=None,
            meta={"outcome": outcome, "to": getattr(issue.status, 'value', issue.status)},
            is_internal=False,
        )

        db.add(issue)
        await db.flush()

        if outcome == "pass":
            await InboxFanOutService().fan_out(
                db=db, trigger=InboxEventType.verified, issue=issue, actor=current_user,
            )
        else:
            # fail/partial — notify assignee + reporter of status change
            await InboxFanOutService().fan_out(
                db=db, trigger=InboxEventType.status_changed, issue=issue, actor=current_user,
                meta={
                    "from": IssueStatus.fixed.value,
                    "to": getattr(issue.status, "value", str(issue.status)),
                },
            )

        return issue

    # ── Reopen ────────────────────────────────────────────────────────────────

    async def reopen(
        self,
        db: AsyncSession,
        issue_id: int,
        current_user: User,
    ) -> Issue:
        """Reopen a closed or verified issue.

        Transitions ``verified | closed → in_progress``.
        """
        from app.services.timeline_service import TimelineService
        from app.services.inbox_service import InboxFanOutService

        issue = await self._get_issue_or_404(db, issue_id)
        if issue.status not in (IssueStatus.verified, IssueStatus.closed):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot reopen issue in status '{issue.status}'.",
            )

        prev_status = issue.status
        issue.status = IssueStatus.in_progress
        issue.verified_at = None

        timeline_svc = TimelineService()
        await timeline_svc.create_event(
            db=db,
            issue_id=issue.id,
            actor_id=current_user.id,
            event_type=TimelineEventType.reopened,
            body=None,
            meta={"from": getattr(prev_status, 'value', prev_status), "to": IssueStatus.in_progress.value},
            is_internal=False,
        )

        db.add(issue)
        await db.flush()

        await InboxFanOutService().fan_out(
            db=db, trigger=InboxEventType.status_changed, issue=issue, actor=current_user,
            meta={
                "from": getattr(prev_status, "value", str(prev_status)),
                "to": IssueStatus.in_progress.value,
            },
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

        Sets ``parent_issue_id`` and transitions to ``closed``.
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
        issue.status = IssueStatus.closed
        issue.closed_at = datetime.now(tz=timezone.utc)

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
        from app.services.timeline_service import TimelineService
        from app.services.inbox_service import InboxFanOutService

        # Lock the row to prevent concurrent diff races
        result = await db.execute(
            select(Issue).where(Issue.id == issue_id).with_for_update()
        )
        issue = result.scalar_one_or_none()
        if issue is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")

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

        # ── Severity ──────────────────────────────────────────────────────────
        if "severity" in payload:
            new_sev = payload["severity"]
            old_sev = getattr(issue.severity, 'value', issue.severity)
            new_sev_val = getattr(new_sev, 'value', new_sev)
            if old_sev != new_sev_val:
                events_to_emit.append((
                    TimelineEventType.severity_changed,
                    {"from": old_sev, "to": new_sev_val},
                ))
                inbox_triggers.append((InboxEventType.severity_changed, {"from": old_sev, "to": new_sev_val}))
                issue.severity = new_sev

        # ── Environment name ──────────────────────────────────────────────────
        if "environment_name" in payload and payload["environment_name"] != issue.environment_name:
            _old_env = issue.environment_name
            _new_env = payload["environment_name"]
            events_to_emit.append((
                TimelineEventType.environment_changed,
                {"from": _old_env, "to": _new_env},
            ))
            inbox_triggers.append((InboxEventType.environment_changed, {"from": _old_env, "to": _new_env}))
            issue.environment_name = _new_env

        # ── Release blocker ───────────────────────────────────────────────────
        if "is_release_blocker" in payload and payload["is_release_blocker"] != issue.is_release_blocker:
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
        if "reproduction_steps" in payload and payload["reproduction_steps"] != issue.reproduction_steps:
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
                    from_rel = await db.execute(select(Release).where(Release.id == issue.release_id))
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

        # ── Status (direct patch, e.g. closing) ───────────────────────────────
        if "status" in payload:
            new_status = payload["status"]
            old_status_val = getattr(issue.status, 'value', issue.status)
            new_status_val = getattr(new_status, 'value', new_status)
            if old_status_val != new_status_val:
                events_to_emit.append((
                    TimelineEventType.status_changed,
                    {"from": old_status_val, "to": new_status_val},
                ))
                if new_status_val != IssueStatus.regression.value:
                    inbox_triggers.append((InboxEventType.status_changed, {"from": old_status_val, "to": new_status_val}))
                issue.status = new_status

                now = datetime.now(tz=timezone.utc)
                if new_status_val == IssueStatus.triaged.value and not issue.triaged_at:
                    issue.triaged_at = now
                    if issue.filed_at:
                        issue.time_to_triage_h = round((now - issue.filed_at).total_seconds() / 3600, 2)
                elif new_status_val == IssueStatus.fixed.value and not issue.fixed_at:
                    issue.fixed_at = now
                    ref = issue.triaged_at or issue.filed_at
                    if ref:
                        issue.time_to_fix_h = round((now - ref).total_seconds() / 3600, 2)
                elif new_status_val == IssueStatus.verified.value and not issue.verified_at:
                    issue.verified_at = now
                    if issue.fixed_at:
                        issue.time_to_verify_h = round((now - issue.fixed_at).total_seconds() / 3600, 2)

                # ── Update active cycle timestamps ─────────────────────────
                from app.db.models.issue_cycle import IssueCycle
                active_cycle_result = await db.execute(
                    select(IssueCycle)
                    .where(IssueCycle.issue_id == issue_id)
                    .order_by(IssueCycle.cycle_number.desc())
                    .limit(1)
                )
                active_cycle = active_cycle_result.scalar_one_or_none()
                if active_cycle:
                    if new_status_val == IssueStatus.triaged.value and not active_cycle.triaged_at:
                        active_cycle.triaged_at = now
                        active_cycle.time_to_triage_h = round(
                            (now - active_cycle.cycle_start_at).total_seconds() / 3600, 2
                        )
                        db.add(active_cycle)
                    elif new_status_val == IssueStatus.fixed.value and not active_cycle.fixed_at:
                        active_cycle.fixed_at = now
                        ref = active_cycle.triaged_at or active_cycle.cycle_start_at
                        active_cycle.time_to_fix_h = round(
                            (now - ref).total_seconds() / 3600, 2
                        )
                        # Retroactively fill time_to_verify_h if verified was
                        # stamped out-of-order (e.g. status jumped to verified
                        # before fixed in the same cycle).
                        if active_cycle.verified_at and active_cycle.time_to_verify_h is None:
                            delta = abs((active_cycle.verified_at - now).total_seconds())
                            active_cycle.time_to_verify_h = round(delta / 3600, 2)
                        db.add(active_cycle)
                    elif new_status_val == IssueStatus.verified.value and not active_cycle.verified_at:
                        active_cycle.verified_at = now
                        if active_cycle.fixed_at:
                            active_cycle.time_to_verify_h = round(
                                (now - active_cycle.fixed_at).total_seconds() / 3600, 2
                            )
                        db.add(active_cycle)

                if new_status_val == IssueStatus.regression.value:
                    from app.db.models.release import Release
                    from app.services.regression_service import regression_service
                    release_result = await db.execute(select(Release).where(Release.id == issue.release_id))
                    release = release_result.scalar_one_or_none()
                    if release:
                        await regression_service.record_regression(db, issue, release, actor)
                    inbox_triggers.append((InboxEventType.regression, None))

        # ── Passthrough fields with no timeline event ─────────────────────────
        for field in ("environment_browser", "environment_os", "environment_build_hash",
                      "environment_staging_url", "curl_command"):
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

        return issue

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
