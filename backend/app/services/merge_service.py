"""MergeService — the one place a merge's effects on the original are written (BR-49, BR-50).

Used by the Duplicate triage outcome (slice 06) and by Report recurrence
(slice 07, ``app/services/recurrence_service.py``).
``merge_into`` runs inside the caller's transaction, so a duplicate's
cancellation and the merge commit or fail together.

Effects, in order:

1. ``recurrence_count += 1`` when the original is a bug — an atomic
   ``UPDATE``, never read-modify-write. Tasks don't count reports (08a).
2. A public comment on the original carrying the merged content, crediting
   the merged report's reporter with an @mention. A tech reporter gets the
   mention notice (it tells them where their report went); a Support reporter
   doesn't — their own ``support_*`` notice already says so. A recurrence
   posts its own comment as a ``recurrence`` event, uncredited: its reporter
   is the actor.
3. The merged report's reporter is subscribed to the original.
4. A status effect by the original's status:

   - ``done`` → the work came back (BR-49, 08a): ``done → todo`` and the
     next cycle starts with the merge comment as its reason — ``release_qa``
     in a Release that hasn't shipped, else ``production`` (and a Released
     release's item moves to the Stream). The assignee gets ``item_returned``;
     Support hears nothing (§13). Same path as ``POST /issues/{id}/returns``.
   - ``cancelled`` → stays cancelled; the triage lead gets
     ``recurrence_on_cancelled``.
   - anything else → no status change.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inbox_item import InboxEventType
from app.db.models.issue import Issue, IssueStatus, IssueType
from app.db.models.issue_subscriber import SubscriptionReason
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.user import User
from app.policy import is_tech

#: The status_changed reason for the Done → To do move a merge makes.
MERGE_RETURN_REASON = "merge"


async def lock_original(db: AsyncSession, issue_id: int) -> Issue | None:
    """Row-lock a merge target, re-reading its current state.

    ``FOR NO KEY UPDATE``, not ``FOR UPDATE``: rows that reference the original
    (subscribers, timeline events) take a ``KEY SHARE`` lock on it, and a
    ``FOR UPDATE`` waiting on another merge's ``KEY SHARE`` deadlocks.
    Callers take it before inserting anything that references the original.
    """
    return (await db.execute(
        select(Issue).where(Issue.id == issue_id, Issue.deleted_at.is_(None))
        .with_for_update(key_share=True)
        .execution_options(populate_existing=True)
    )).scalar_one_or_none()


@dataclass
class MergeResult:
    original: Issue
    #: The public timeline event carrying the merged content.
    comment: IssueTimeline


class MergeService:

    async def merge_into(
        self,
        db: AsyncSession,
        original: Issue,
        *,
        content_md: str,
        reporter_id: int | None,
        attachments: Sequence = (),
        actor: User,
        merged_issue_id: int | None = None,
        reason: SubscriptionReason,
        comment_meta: dict | None = None,
        event_type: TimelineEventType = TimelineEventType.comment,
        credit_reporter: bool = True,
    ) -> MergeResult:
        """Apply the merge effects to ``original``; return it, refreshed, with the comment.

        ``attachments`` are pending uploads (``PendingAttachment``-shaped) to
        attach to the original — recurrence (07) passes them; the Duplicate
        outcome leaves the duplicate's own attachments where they are.
        """
        from app.db.models.issue_attachment import IssueAttachment
        from app.services.inbox_service import InboxFanOutService
        from app.services.issue_service import issue_service
        from app.services.subscriber_service import subscribe
        from app.services.timeline_service import TimelineService

        # Serialize merges into the same original: the status effect below
        # reads the original's status and must not act on a stale one.
        original = await lock_original(db, original.id)

        if getattr(original.type, "value", original.type) == IssueType.bug.value:
            await db.execute(
                update(Issue)
                .where(Issue.id == original.id)
                .values(recurrence_count=Issue.recurrence_count + 1)
            )
            await db.refresh(original, ["recurrence_count"])

        reporter = await db.get(User, reporter_id) if reporter_id and credit_reporter else None
        if reporter is not None:
            content_md = f"{content_md}\n\nReported by @{reporter.username}"
        comment = await TimelineService().create_event(
            db=db,
            issue_id=original.id,
            actor_id=actor.id,
            event_type=event_type,
            body=content_md,
            meta=comment_meta,
            is_internal=False,
            mentioned_user_ids=[reporter.id] if reporter is not None else None,
        )
        for pending in attachments:
            db.add(IssueAttachment(
                issue_id=original.id,
                uploaded_by_id=reporter_id or actor.id,
                file_name=pending.filename,
                s3_key=pending.s3_key,
                mime_type=pending.mime_type,
                file_size_bytes=pending.file_size_bytes,
                attachment_type=pending.attachment_type,
            ))

        await subscribe(db, original.id, reporter_id, reason)
        await db.flush()

        if reporter is not None and is_tech(reporter.role):
            await InboxFanOutService().fan_out(
                db=db, trigger=InboxEventType.mention, issue=original, actor=actor,
                timeline_event=comment,
                extra_meta={"mentioned_user_ids": [str(reporter.id)], "body": content_md},
                meta={"body_snippet": content_md[:200]},
            )

        status = getattr(original.status, "value", original.status)
        if status == IssueStatus.done.value:
            original = await issue_service.send_back_done(
                db, original, actor, comment,
                merged_issue_id=merged_issue_id, reason_label=MERGE_RETURN_REASON,
            )
        elif status == IssueStatus.cancelled.value:
            await InboxFanOutService().fan_out(
                db=db, trigger=InboxEventType.recurrence_on_cancelled, issue=original, actor=actor,
            )

        return MergeResult(original=original, comment=comment)


merge_service = MergeService()
