"""InboxFanOutService — creates per-user InboxItem rows and pushes WebSocket events.

Fan-out notification matrix
----------------------------
Event                → Who receives an inbox item
------               → -----------------------------------
assigned             → assignee
fixed                → reporter + triage_lead users
comment              → reporter + assignee (if different from actor)
mention              → mentioned users (parsed from body)
regression           → reporter + assignee + triage leads
blocker_filed        → all triage leads + CTOs
blocker_cleared      → all triage leads + CTOs + assignee + reporter
status_changed       → assignee + reporter
verified             → reporter + assignee
filed                → triage leads
environment_changed  → assignee + reporter
release_changed      → assignee + reporter
attachment_added     → assignee + reporter
"""

import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.inbox_item import InboxItem, InboxEventType
from app.db.models.issue import Issue
from app.db.models.issue_timeline import IssueTimeline
from app.db.models.user import User, UserRole

logger = logging.getLogger(__name__)

# Regex to find @username mentions in comment bodies
_MENTION_RE = re.compile(r"@([a-z0-9_.-]+)", re.IGNORECASE)


class InboxFanOutService:
    """Creates ``InboxItem`` rows for the relevant audience of each event."""

    async def fan_out(
        self,
        db: AsyncSession,
        trigger: InboxEventType,
        issue: Issue,
        actor: User,
        timeline_event: IssueTimeline | None = None,
        extra_meta: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> list[InboxItem]:
        """Create inbox items for all users who should be notified.

        Parameters
        ----------
        db:
            Active async session (items are flushed but not committed).
        trigger:
            The ``InboxEventType`` driving the notification.
        issue:
            The issue the event relates to.
        actor:
            The user who performed the action (excluded from their own inbox).
        timeline_event:
            Optional linked timeline entry (stored for deep-link support).
        extra_meta:
            Additional context for mention detection (e.g. comment body).

        Returns
        -------
        list[InboxItem]
            All newly created inbox items (already added to the session).
        """
        recipients: set[str] = set()  # collect user IDs as strings to avoid duplicates
        # Users in this set always receive a notification, even if they are the actor
        # (e.g. self-assignment — you assigned it to yourself, you should still see it).
        forced_recipients: set[str] = set()

        # ── Determine recipient set by trigger type ────────────────────────────
        if trigger == InboxEventType.assigned:
            if issue.assignee_id:
                # Use forced_recipients so self-assignment still creates a notification.
                forced_recipients.add(str(issue.assignee_id))

        elif trigger == InboxEventType.fixed:
            # Notify the reporter
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))
            # Notify all triage leads
            triage_leads = await self._users_with_role(db, UserRole.triage_lead)
            recipients.update(str(u.id) for u in triage_leads)

        elif trigger == InboxEventType.comment:
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))
            # Prefer 'mention' over 'comment': mentioned users are excluded here
            # and will receive a separate mention notification instead.
            for uid in (extra_meta or {}).get("mentioned_user_ids", []):
                recipients.discard(str(uid))

        elif trigger == InboxEventType.mention:
            _mention_extra = extra_meta or {}
            # Fast path: explicit user IDs provided by the comment route
            explicit_ids = _mention_extra.get("mentioned_user_ids", [])
            logger.info("[fan_out] mention trigger explicit_ids=%s meta_keys=%s", explicit_ids, list(_mention_extra.keys()))
            if explicit_ids:
                recipients.update(str(uid) for uid in explicit_ids)
                logger.info("[fan_out] mention fast-path recipients from explicit_ids=%s", explicit_ids)
            else:
                # Fallback: parse @username mentions from comment body
                body = _mention_extra.get("body", "")
                mentioned_usernames = [u.lower() for u in _MENTION_RE.findall(body)]
                logger.info("[fan_out] mention regex fallback body_len=%d found_usernames=%s", len(body), mentioned_usernames)
                if mentioned_usernames:
                    result = await db.execute(
                        select(User).where(User.username.in_(mentioned_usernames))
                    )
                    matched_users = list(result.scalars().all())
                    logger.info("[fan_out] mention DB matched %d users for usernames=%s", len(matched_users), mentioned_usernames)
                    for user in matched_users:
                        recipients.add(str(user.id))
                else:
                    logger.warning("[fan_out] mention fallback: no @usernames found in body")

        elif trigger == InboxEventType.regression:
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))
            leads = await self._users_with_role(db, UserRole.triage_lead)
            recipients.update(str(u.id) for u in leads)

        elif trigger == InboxEventType.status_changed:
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))

        elif trigger == InboxEventType.verified:
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))

        elif trigger == InboxEventType.filed:
            leads = await self._users_with_role(db, UserRole.triage_lead)
            recipients.update(str(u.id) for u in leads)

        elif trigger == InboxEventType.blocker_filed:
            leads = await self._users_with_role(db, UserRole.triage_lead)
            ctos = await self._users_with_role(db, UserRole.cto)
            admins = await self._users_with_role(db, UserRole.admin)
            recipients.update(str(u.id) for u in leads + ctos + admins)

        elif trigger == InboxEventType.blocker_cleared:
            leads = await self._users_with_role(db, UserRole.triage_lead)
            ctos = await self._users_with_role(db, UserRole.cto)
            admins = await self._users_with_role(db, UserRole.admin)
            recipients.update(str(u.id) for u in leads + ctos + admins)
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))

        elif trigger in (
            InboxEventType.environment_changed,
            InboxEventType.release_changed,
            InboxEventType.attachment_added,
        ):
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))

        # Remove the actor — they don't get notified of their own actions,
        # then re-add any forced recipients (e.g. self-assignment).
        logger.info("[fan_out] trigger=%s recipients_before_discard=%s actor_id=%s", trigger, recipients, actor.id)
        recipients.discard(str(actor.id))
        recipients.update(forced_recipients)
        logger.info("[fan_out] trigger=%s final_recipients=%s", trigger, recipients)

        # ── Create InboxItem rows ─────────────────────────────────────────────
        items: list[InboxItem] = []
        for user_id_str in recipients:
            item = InboxItem(
                user_id=int(user_id_str),
                actor_id=actor.id,
                issue_id=issue.id,
                timeline_id=timeline_event.id if timeline_event else None,
                event_type=trigger,
                is_read=False,
                meta=meta,
            )
            db.add(item)
            items.append(item)

        await db.flush()

        # ── Push real-time WebSocket events via Redis ─────────────────────────
        await self._push_redis(trigger, issue, items)

        return items

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    async def _users_with_role(db: AsyncSession, role: UserRole) -> list[User]:
        """Return all active users with the given role."""
        result = await db.execute(
            select(User).where(User.role == role, User.is_active.is_(True))
        )
        return list(result.scalars().all())

    @staticmethod
    async def _push_redis(
        trigger: InboxEventType,
        issue: Issue,
        items: list[InboxItem],
    ) -> None:
        """Publish a lightweight WebSocket push payload to Redis pub/sub.

        Each recipient's inbox WebSocket channel receives a message so the
        frontend can update the unread badge without polling.
        """
        try:
            from app.core.redis_client import publish

            for item in items:
                await publish(
                    f"ws:inbox:{item.user_id}",
                    {
                        "type": "inbox_item",
                        "event_type": trigger.value,
                        "issue_id": str(issue.id),
                        "issue_number": issue.issue_number,
                        "item_id": str(item.id),
                    },
                )
        except Exception:
            # Redis push is best-effort — do not fail the request if Redis is down
            pass


# Module-level singleton
inbox_service = InboxFanOutService()
