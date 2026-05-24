"""IssueService — domain logic for creating and advancing issues.

All public methods are ``async`` and accept an ``AsyncSession`` as their first
argument so they can be composed inside a single DB transaction when needed.
"""

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.issue import Issue, IssueSeverity, IssueStatus
from app.db.models.issue_timeline import TimelineEventType
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

        Parameters
        ----------
        db:
            Active async session (will be flushed but not committed).
        data:
            Validated ``IssueCreate`` payload.
        current_user:
            The authenticated user filing the issue (becomes the reporter).

        Returns
        -------
        Issue
            The newly created, flushed (but not committed) ``Issue`` row.
        """
        from app.db.models.release import Release
        from app.services.timeline_service import TimelineService

        # Resolve the release to get the project_id
        release_result = await db.execute(
            select(Release).where(Release.id == data.release_id)
        )
        release = release_result.scalar_one_or_none()
        if release is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")

        now = datetime.now(tz=timezone.utc)

        # Convert reproduction steps to dict list for JSON storage
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
            curl_command=data.curl_command,
            reporter_id=current_user.id,
            status=IssueStatus.new,
            filed_at=now,
            reproduction_steps=reproduction_steps_json or [],
        )
        db.add(issue)
        await db.flush()  # get issue.id before adding timeline + attachments

        # Timeline: filed event
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

        # Link any pre-uploaded attachments to this issue
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
        return issue

    # ── Triage ────────────────────────────────────────────────────────────────

    async def triage(
        self,
        db: AsyncSession,
        issue_id: uuid.UUID,
        assignee_id: uuid.UUID,
        severity: IssueSeverity,
        current_user: User,
        labels: list[str] | None = None,
        is_release_blocker: bool | None = None,
    ) -> Issue:
        """Triage an issue: assign it and set severity.

        Transitions status ``new → triaged``.  Also computes ``time_to_triage_h``
        from ``filed_at`` → now.

        Parameters
        ----------
        db:
            Active async session.
        issue_id:
            UUID of the issue to triage.
        assignee_id:
            UUID of the user being assigned the issue.
        severity:
            Confirmed severity after triage.
        current_user:
            The triage lead performing the action.

        Returns
        -------
        Issue
            Updated issue row.
        """
        from app.services.timeline_service import TimelineService

        issue = await self._get_issue_or_404(db, issue_id)
        if issue.status not in (IssueStatus.new,):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot triage an issue in status '{issue.status}'",
            )

        now = datetime.now(tz=timezone.utc)
        prev_severity = issue.severity

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
            meta={"assignee_id": str(assignee_id)},
            is_internal=False,
        )

        db.add(issue)
        await db.flush()
        return issue

    # ── Fix ───────────────────────────────────────────────────────────────────

    async def mark_fixed(
        self,
        db: AsyncSession,
        issue_id: uuid.UUID,
        mr_url: str | None,
        current_user: User,
    ) -> Issue:
        """Mark an issue as fixed (developer submits MR).

        Transitions ``triaged | in_progress → fixed``.

        Parameters
        ----------
        db:
            Active async session.
        issue_id:
            UUID of the issue being fixed.
        mr_url:
            Optional GitLab / GitHub merge-request URL.
        current_user:
            The developer marking the fix.

        Returns
        -------
        Issue
            Updated issue row.
        """
        from app.services.timeline_service import TimelineService

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
        return issue

    # ── Verify ────────────────────────────────────────────────────────────────

    async def verify_fix(
        self,
        db: AsyncSession,
        issue_id: uuid.UUID,
        outcome: str,  # "pass" | "fail" | "partial"
        current_user: User,
    ) -> Issue:
        """QA verifies a developer's fix.

        - ``pass`` → transitions to ``verified``
        - ``fail`` → transitions back to ``in_progress``
        - ``partial`` → stays ``fixed`` with a timeline comment

        Parameters
        ----------
        db, issue_id, outcome, current_user:
            As described above.

        Returns
        -------
        Issue
            Updated issue row.
        """
        from app.services.timeline_service import TimelineService

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
        return issue

    # ── Reopen ────────────────────────────────────────────────────────────────

    async def reopen(
        self,
        db: AsyncSession,
        issue_id: uuid.UUID,
        current_user: User,
    ) -> Issue:
        """Reopen a closed or verified issue.

        Transitions ``verified | closed → in_progress``.

        Parameters
        ----------
        db, issue_id, current_user:
            Standard arguments.

        Returns
        -------
        Issue
            Updated issue row.
        """
        from app.services.timeline_service import TimelineService

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
            event_type=TimelineEventType.status_changed,
            body="Issue reopened.",
            meta={"from": getattr(prev_status, 'value', prev_status), "to": IssueStatus.in_progress.value},
            is_internal=False,
        )

        db.add(issue)
        await db.flush()
        return issue

    # ── Duplicate linking ─────────────────────────────────────────────────────

    async def link_duplicate(
        self,
        db: AsyncSession,
        issue_id: uuid.UUID,
        parent_id: uuid.UUID,
        current_user: User,
    ) -> Issue:
        """Mark ``issue_id`` as a duplicate of ``parent_id``.

        Sets ``parent_issue_id`` and transitions to ``closed``.

        Parameters
        ----------
        db, issue_id, parent_id, current_user:
            Standard arguments.

        Returns
        -------
        Issue
            Updated duplicate issue row.
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

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    async def _get_issue_or_404(db: AsyncSession, issue_id: uuid.UUID) -> Issue:
        """Fetch an issue by UUID or raise 404."""
        result = await db.execute(select(Issue).where(Issue.id == issue_id))
        issue = result.scalar_one_or_none()
        if issue is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found")
        return issue


# Module-level singleton
issue_service = IssueService()
