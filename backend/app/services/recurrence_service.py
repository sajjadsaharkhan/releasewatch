"""RecurrenceService — Report recurrence on a bug (slice 07, FR-13–16, BR-22/23).

A recurrence records one more occurrence of an open or Cancelled bug instead
of a duplicate report. Its effects go through ``MergeService.merge_into``
(BR-50), in the caller's transaction:

1. ``recurrence_count += 1`` (atomic — two concurrent recurrences both count, AC-13).
2. A public ``recurrence`` timeline event with the comment as body.
3. An ``issue_recurrences`` row (for reports over time, slice 11).
4. The reporter is subscribed to the bug's Support notices (reason ``recurrence``).
5. On a Cancelled bug, the triage lead gets ``recurrence_on_cancelled`` and the
   bug stays Cancelled (FR-15). On an open bug, the assignee and reporter get
   the ordinary ``comment`` notice.

Done bugs and tasks are refused by Policy (``recurrence_on_done``,
``recurrence_bug_only``) — re-checked here on the locked row, so a bug that
reached Done a moment ago can't take one.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inbox_item import InboxEventType
from app.db.models.issue import Issue, IssueStatus
from app.db.models.issue_recurrence import IssueRecurrence
from app.db.models.issue_subscriber import SubscriptionReason
from app.db.models.issue_timeline import TimelineEventType
from app.db.models.user import User
from app.policy import Action
from app.schemas.issue import RecurrenceCreate
from app.services.authz import authorize, issue_target
from app.services.inbox_service import InboxFanOutService
from app.services.merge_service import lock_original, merge_service


class RecurrenceService:

    async def report(
        self, db: AsyncSession, issue: Issue, payload: RecurrenceCreate, actor: User,
    ) -> Issue:
        project = issue.__dict__.get("project")
        locked = await lock_original(db, issue.id)
        authorize(actor, Action.report_recurrence, issue_target(locked, project))

        result = await merge_service.merge_into(
            db, locked,
            content_md=payload.comment,
            reporter_id=actor.id,
            attachments=payload.pending_attachments,
            source_release_id=None,
            actor=actor,
            reason=SubscriptionReason.recurrence,
            event_type=TimelineEventType.recurrence,
            credit_reporter=False,
        )
        original, comment = result.original, result.comment
        comment.meta = {**(comment.meta or {}), "recurrence_count": original.recurrence_count}
        db.add(IssueRecurrence(
            issue_id=original.id, reported_by_id=actor.id, timeline_id=comment.id,
        ))
        await db.flush()

        status = getattr(original.status, "value", original.status)
        if status != IssueStatus.cancelled.value:
            body = payload.comment
            snippet = (body[:200] + "…") if len(body) > 200 else body
            await InboxFanOutService().fan_out(
                db=db, trigger=InboxEventType.comment, issue=original, actor=actor,
                timeline_event=comment,
                extra_meta={"body": body, "mentioned_user_ids": []},
                meta={"body_snippet": snippet, "recurrence": True},
            )
        return original


recurrence_service = RecurrenceService()
