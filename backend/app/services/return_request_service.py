"""ReturnRequestService — Problem is back (slice 20, PRD v3.1 §8.10, FR-68/69, BR-69–71).

The only writer of ``return_requests``. A Support user presses **Problem is
back** on a Done item: a public comment, a Pending request, a subscription, and
a notice to the triage lead. The item stays Done and nothing is counted. A tech
user then:

- **confirms** — the ordinary Reject from Done (``IssueService.reject_with``),
  with the request's first comment as the cycle's reason; or
- **dismisses** — a public comment explaining why; nothing else changes.

An item has at most one Pending request: ``request`` re-reads under the item's
row lock, and a partial unique index backs it. A request is closed as
Confirmed, without a notice, when its item leaves Done by any other path (a
tech Reject, a merge into it, a cancel) — it came back anyway.
"""

from datetime import UTC, datetime

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.db.models.inbox_item import InboxEventType
from app.db.models.issue import Issue, IssueStatus, issue_key
from app.db.models.issue_subscriber import SubscriptionReason
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.return_request import (
    ReturnRequest, ReturnRequestEntry, ReturnRequestStatus,
)
from app.db.models.user import User
from app.schemas.issue import PendingReturnRequest, ReturnRequestEntryResponse, UserSummary
from app.schemas.return_request import (
    ReturnRequestCreate, ReturnRequestFirstComment, ReturnRequestItemCard, ReturnRequestQueue,
    ReturnRequestQueueRow, ReturnRequestResponse,
)
from app.services.merge_service import lock_original


def _snippet(body: str | None) -> str | None:
    if body and len(body) > 200:
        return body[:200] + "…"
    return body


class ReturnRequestService:

    # ── Reads ─────────────────────────────────────────────────────────────────

    async def pending_for(self, db: AsyncSession, issue_id: int) -> ReturnRequest | None:
        return (await db.execute(
            select(ReturnRequest).where(
                ReturnRequest.issue_id == issue_id,
                ReturnRequest.status == ReturnRequestStatus.pending.value,
            ).execution_options(populate_existing=True)
        )).scalar_one_or_none()

    async def get(self, db: AsyncSession, request_id: int) -> ReturnRequest | None:
        return (await db.execute(
            select(ReturnRequest).where(ReturnRequest.id == request_id)
            .execution_options(populate_existing=True)
        )).scalar_one_or_none()

    async def bodies(self, db: AsyncSession, comment_ids: set[int]) -> dict[int, IssueTimeline]:
        if not comment_ids:
            return {}
        rows = await db.execute(select(IssueTimeline).where(IssueTimeline.id.in_(comment_ids)))
        return {t.id: t for t in rows.scalars().all()}

    # ── Problem is back ───────────────────────────────────────────────────────

    async def request(
        self, db: AsyncSession, issue: Issue, actor: User, payload: ReturnRequestCreate,
    ) -> ReturnRequest:
        """Record one press. Policy was checked by the route; the item's status is
        re-checked here on the locked row, so a Done item that was just rejected
        can't take a request."""
        from app.services.attachment_service import attachment_service
        from app.services.inbox_service import InboxFanOutService
        from app.services.subscriber_service import subscribe
        from app.services.timeline_service import TimelineService

        locked = await lock_original(db, issue.id)
        if locked is None or getattr(locked.status, "value", locked.status) != IssueStatus.done.value:
            raise DomainError(
                status.HTTP_409_CONFLICT, "Problem is back applies to Done items only.", "not_done",
            )

        timeline = TimelineService()
        existing = await self.pending_for(db, locked.id)
        comment = await timeline.create_event(
            db=db, issue_id=locked.id, actor_id=actor.id,
            event_type=TimelineEventType.comment, body=payload.comment,
            meta={"return_request": True}, is_internal=False,
        )
        for pending in payload.pending_attachments:
            await attachment_service.add_pending(db, locked.id, actor.id, pending)

        first = existing is None
        if first:
            request = ReturnRequest(
                issue_id=locked.id, status=ReturnRequestStatus.pending.value,
                requested_by_id=actor.id, start_comment_id=comment.id,
            )
            db.add(request)
            await db.flush()
        else:
            request = existing
        db.add(ReturnRequestEntry(request_id=request.id, user_id=actor.id, comment_id=comment.id))
        await db.flush()

        comment.meta = {**(comment.meta or {}), "return_request_id": request.id}
        await timeline.create_event(
            db=db, issue_id=locked.id, actor_id=actor.id,
            event_type=(
                TimelineEventType.return_requested if first
                else TimelineEventType.return_request_added
            ),
            body=None, meta={"request_id": request.id, "comment_id": comment.id},
            is_internal=False,
        )
        await subscribe(db, locked.id, actor.id, SubscriptionReason.return_request)
        await db.flush()

        if first:
            await InboxFanOutService().fan_out(
                db=db, trigger=InboxEventType.return_requested, issue=locked, actor=actor,
                timeline_event=comment,
                meta={"body_snippet": _snippet(payload.comment), "request_id": request.id},
            )
        await db.refresh(request, ["entries"])
        return request

    # ── Deciding ──────────────────────────────────────────────────────────────

    async def _lock_pending(self, db: AsyncSession, request_id: int) -> tuple[ReturnRequest, Issue]:
        request = await self.get(db, request_id)
        if request is None:
            raise DomainError(status.HTTP_404_NOT_FOUND, "Return request not found.", "not_found")
        issue = await lock_original(db, request.issue_id)
        request = await self.get(db, request_id)  # re-read under the item's lock
        if request.status != ReturnRequestStatus.pending.value:
            raise DomainError(
                status.HTTP_409_CONFLICT, "This request was already decided.", "request_closed",
            )
        return request, issue

    @staticmethod
    def _close(request: ReturnRequest, outcome: ReturnRequestStatus, actor: User) -> None:
        request.status = outcome.value
        request.decided_by_id = actor.id
        request.decided_at = datetime.now(tz=UTC)

    async def _notify_requesters(
        self, db: AsyncSession, request: ReturnRequest, issue: Issue, actor: User,
        outcome: str, comment: IssueTimeline | None,
    ) -> None:
        from app.services.inbox_service import InboxFanOutService

        body = comment.body if comment is not None else None
        await InboxFanOutService().fan_out(
            db=db, trigger=InboxEventType.support_return_decided, issue=issue, actor=actor,
            timeline_event=comment,
            extra_meta={"recipient_ids": sorted({e.user_id for e in request.entries if e.user_id})},
            meta={"outcome": outcome, "comment": body, "body_snippet": _snippet(body),
                  "request_id": request.id},
        )

    async def confirm(self, db: AsyncSession, request_id: int, actor: User) -> ReturnRequest:
        from app.services.issue_service import issue_service
        from app.services.timeline_service import TimelineService

        request, issue = await self._lock_pending(db, request_id)
        # Closed first, so the item leaving Done below finds nothing Pending.
        self._close(request, ReturnRequestStatus.confirmed, actor)
        await db.flush()
        await TimelineService().create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.return_confirmed, body=None,
            meta={"request_id": request.id}, is_internal=False,
        )
        request.item_already_returned = False
        if getattr(issue.status, "value", issue.status) == IssueStatus.done.value:
            start = await db.get(IssueTimeline, request.start_comment_id)
            await issue_service.reject_with(
                db, issue, actor, start, move_reason="return_request",
            )
            await self._notify_requesters(db, request, issue, actor, "confirmed", None)
        else:
            request.item_already_returned = True
        await db.flush()
        return request

    async def dismiss(
        self, db: AsyncSession, request_id: int, actor: User, comment: str | None,
    ) -> ReturnRequest:
        from app.services.timeline_service import TimelineService

        text = (comment or "").strip()
        if not text:
            raise DomainError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Say why the item stays Done.", "reason_required",
            )
        request, issue = await self._lock_pending(db, request_id)
        timeline = TimelineService()
        decision = await timeline.create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.comment, body=text,
            meta={"return_request_id": request.id}, is_internal=False,
        )
        self._close(request, ReturnRequestStatus.dismissed, actor)
        request.decision_comment_id = decision.id
        await db.flush()
        await timeline.create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.return_dismissed, body=None,
            meta={"request_id": request.id, "comment_id": decision.id}, is_internal=False,
        )
        await self._notify_requesters(db, request, issue, actor, "dismissed", decision)
        await db.flush()
        return request

    async def close_when_item_leaves_done(
        self, db: AsyncSession, issue: Issue, actor: User,
    ) -> None:
        """The item came back by another path (a Reject, a merge, a cancel): the
        Pending request, if any, is Confirmed by that actor, with no extra notice."""
        from app.services.timeline_service import TimelineService

        request = await self.pending_for(db, issue.id)
        if request is None:
            return
        self._close(request, ReturnRequestStatus.confirmed, actor)
        await db.flush()
        await TimelineService().create_event(
            db=db, issue_id=issue.id, actor_id=actor.id,
            event_type=TimelineEventType.return_confirmed, body=None,
            meta={"request_id": request.id, "via": "item_left_done"}, is_internal=False,
        )

    # ── Response shapes ───────────────────────────────────────────────────────

    def _entries(
        self, request: ReturnRequest, bodies: dict[int, IssueTimeline],
    ) -> list[ReturnRequestEntryResponse]:
        return [
            ReturnRequestEntryResponse(
                id=e.id,
                user=UserSummary.model_validate(e.user) if e.user else None,
                comment_id=e.comment_id,
                body=bodies[e.comment_id].body if e.comment_id in bodies else None,
                created_at=e.created_at,
            )
            for e in request.entries
        ]

    async def to_response(self, db: AsyncSession, request: ReturnRequest) -> ReturnRequestResponse:
        bodies = await self.bodies(db, {e.comment_id for e in request.entries if e.comment_id})
        return ReturnRequestResponse(
            id=request.id, issue_id=request.issue_id, status=request.status,
            requested_by=(
                UserSummary.model_validate(request.requested_by) if request.requested_by else None
            ),
            requested_at=request.requested_at, start_comment_id=request.start_comment_id,
            entries=self._entries(request, bodies),
            decided_by=UserSummary.model_validate(request.decided_by) if request.decided_by else None,
            decided_at=request.decided_at, decision_comment_id=request.decision_comment_id,
            item_already_returned=bool(getattr(request, "item_already_returned", False)),
        )

    async def list_for_issue(self, db: AsyncSession, issue_id: int) -> list[ReturnRequestResponse]:
        rows = (await db.execute(
            select(ReturnRequest).where(ReturnRequest.issue_id == issue_id)
            .order_by(ReturnRequest.requested_at.desc(), ReturnRequest.id.desc())
            .execution_options(populate_existing=True)
        )).scalars().all()
        return [await self.to_response(db, r) for r in rows]

    async def pending_map(
        self, db: AsyncSession, issue_ids: list[int],
    ) -> dict[int, PendingReturnRequest]:
        """The Pending request of each item that has one (``IssueResponse.pending_return_request``)."""
        if not issue_ids:
            return {}
        rows = (await db.execute(
            select(ReturnRequest).where(
                ReturnRequest.issue_id.in_(issue_ids),
                ReturnRequest.status == ReturnRequestStatus.pending.value,
            ).execution_options(populate_existing=True)
        )).scalars().all()
        bodies = await self.bodies(
            db, {e.comment_id for r in rows for e in r.entries if e.comment_id},
        )
        return {
            r.issue_id: PendingReturnRequest(
                id=r.id, requested_at=r.requested_at, entries=self._entries(r, bodies),
            )
            for r in rows
        }

    async def pending_issue_ids(self, db: AsyncSession, issue_ids: list[int]) -> set[int]:
        if not issue_ids:
            return set()
        rows = await db.execute(
            select(ReturnRequest.issue_id).where(
                ReturnRequest.issue_id.in_(issue_ids),
                ReturnRequest.status == ReturnRequestStatus.pending.value,
            )
        )
        return set(rows.scalars().all())

    async def queue(
        self, db: AsyncSession, project_id: int | None = None,
    ) -> ReturnRequestQueue:
        """Pending requests — a project's, or every project's — oldest first, with
        the item card (FR-69)."""
        from sqlalchemy.orm import selectinload

        rows = (await db.execute(
            select(ReturnRequest).join(Issue, Issue.id == ReturnRequest.issue_id)
            .where(
                Issue.deleted_at.is_(None),
                ReturnRequest.status == ReturnRequestStatus.pending.value,
                *([Issue.project_id == project_id] if project_id is not None else []),
            )
            .order_by(ReturnRequest.requested_at.asc(), ReturnRequest.id.asc())
            .execution_options(populate_existing=True)
        )).scalars().all()
        issues = {}
        if rows:
            found = await db.execute(
                select(Issue).where(Issue.id.in_([r.issue_id for r in rows])).options(
                    selectinload(Issue.assignee), selectinload(Issue.release),
                    selectinload(Issue.project),
                ).execution_options(populate_existing=True)
            )
            issues = {i.id: i for i in found.scalars().all()}
        bodies = await self.bodies(
            db, {e.comment_id for r in rows for e in r.entries if e.comment_id},
        )
        items = []
        for r in rows:
            issue = issues[r.issue_id]
            release = issue.release
            first = bodies.get(r.start_comment_id)
            seen: dict[int, UserSummary] = {}
            for e in r.entries:
                if e.user and e.user.id not in seen:
                    seen[e.user.id] = UserSummary.model_validate(e.user)
            items.append(ReturnRequestQueueRow(
                id=r.id, requested_at=r.requested_at,
                issue=ReturnRequestItemCard(
                    id=issue.id, issue_number=issue.issue_number,
                    key=issue_key(issue.type, issue.issue_number), title=issue.title,
                    status=getattr(issue.status, "value", issue.status),
                    project_id=issue.project_id, release_id=issue.release_id,
                    release_version=release.version if release else None,
                    container_kind=getattr(release.kind, "value", release.kind) if release else None,
                    release_status=(
                        getattr(release.status, "value", release.status) if release else None
                    ),
                    project_slug=issue.project.slug if issue.project else None,
                    project_name=issue.project.name if issue.project else None,
                    assignee_user=(
                        UserSummary.model_validate(issue.assignee) if issue.assignee else None
                    ),
                    done_at=issue.completed_at,
                ),
                requesters=list(seen.values()),
                first_comment=ReturnRequestFirstComment(
                    id=first.id if first else None,
                    body=first.body if first else None,
                    created_at=first.created_at if first else None,
                ),
                entry_count=len(r.entries),
            ))
        return ReturnRequestQueue(items=items, total=len(items))


return_request_service = ReturnRequestService()
