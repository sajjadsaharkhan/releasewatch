"""InboxFanOutService — creates per-user InboxItem rows and pushes WebSocket events.

Fan-out notification matrix
----------------------------
Event                → Who receives an inbox item
------               → -----------------------------------
assigned             → assignee
fixed                → reporter + triage_lead users
comment              → reporter + assignee (if different from actor)
mention              → mentioned users (parsed from body)
item_returned        → assignee (08a: work came back — reason + comment)
blocker_filed        → all triage leads + CTOs
blocker_cleared      → all triage leads + CTOs + assignee + reporter
status_changed       → assignee + reporter
verified             → reporter + assignee
filed                → triage leads
environment_changed  → assignee + reporter
release_changed      → assignee + reporter + triage_lead (new release's triage lead)
project_changed      → assignee + reporter + triage_lead
attachment_added     → assignee + reporter
priority_changed     → assignee + reporter + triage_lead
needs_info_replied   → triage leads (slice 06, FR-19)
moved_into_project   → the new project's triage leads (slice 06, FR-20)
recurrence_on_cancelled → triage leads (a merge or recurrence on a Cancelled item)
support_needs_info   → Support-role subscribers (slice 06, §13)
support_cancelled    → Support-role subscribers
support_done         → Support-role subscribers
release_shipped      → the release's item assignees + active CTOs (slice 09, ``fan_out_release``)
release_overdue      → active CTOs (slice 09, ``fan_out_release``)

"triage leads" is the project's active triage lead, or every active admin
while the project has none (AC-23). Whatever the event, a recipient who may
not see the item — or, for an internal note, anyone who isn't a tech role —
is dropped before any row, WebSocket push, or Telegram send exists
(slice 04, BR-30/31). Support users are also dropped from every event except
the three ``support_*`` ones and ``mention`` (slice 06), so Support never gets
internal content by notification.
"""

import html as html_lib
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.notification_defaults import resolve_matrix
from app.db.models.inbox_item import (
    ASSIGNEE_EVENTS, SUPPORT_EVENTS, SUPPORT_RECEIVABLE, InboxItem, InboxEventType,
)
from app.db.models.issue import Issue, IssueSource
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
        actor: User | None,
        timeline_event: IssueTimeline | None = None,
        extra_meta: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        suppress_user_ids: set[str] | None = None,
        delay_seconds: int = 0,
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
            The user who performed the action (excluded from their own inbox);
            ``None`` for a scheduled notice (the due-date job, slice 10).
        timeline_event:
            Optional linked timeline entry (stored for deep-link support).
        extra_meta:
            Additional context for mention detection (e.g. comment body).
        suppress_user_ids:
            Recipients to drop before any item is created or Telegram queued —
            used to collapse repeat reaction notifications on one comment.
        delay_seconds:
            Hold the Telegram send for this long, giving the actor a window to
            undo. Applies to both the queued task and the beat-task retry clock.

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
            # Notify all triage leads (role-based + release triage lead)
            triage_leads = await self._triage_recipients(db, issue)
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

        elif trigger == InboxEventType.reaction:
            # Fixed audience, deliberately not matrix-configurable: the author of
            # the reacted-to comment, anyone they @mentioned in it, and the
            # issue's assignee.
            if timeline_event is not None:
                if timeline_event.actor_id:
                    recipients.add(str(timeline_event.actor_id))
                for uid in (timeline_event.meta or {}).get("mentioned_user_ids", []):
                    recipients.add(str(uid))
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))

        elif trigger == InboxEventType.item_returned:
            # The person whose queue it lands back in (FR-65). Support never
            # gets it — fan_out drops Support from every non-Support event.
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))

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
            leads = await self._triage_recipients(db, issue)
            recipients.update(str(u.id) for u in leads)

        elif trigger == InboxEventType.blocker_filed:
            leads = await self._triage_recipients(db, issue)
            ctos = await self._users_with_role(db, UserRole.cto)
            admins = await self._users_with_role(db, UserRole.admin)
            recipients.update(str(u.id) for u in leads + ctos + admins)

        elif trigger == InboxEventType.blocker_cleared:
            leads = await self._triage_recipients(db, issue)
            ctos = await self._users_with_role(db, UserRole.cto)
            admins = await self._users_with_role(db, UserRole.admin)
            recipients.update(str(u.id) for u in leads + ctos + admins)
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))

        elif trigger == InboxEventType.needs_clarification:
            # Only the reporter needs to act — notify them directly.
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))

        elif trigger == InboxEventType.release_changed:
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))
            # Notify the new release's triage lead — issue.release_id is already
            # updated to the destination release by the time fan_out is called.
            leads = await self._triage_recipients(db, issue)
            recipients.update(str(u.id) for u in leads)

        elif trigger == InboxEventType.project_changed:
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))
            leads = await self._triage_recipients(db, issue)
            recipients.update(str(u.id) for u in leads)

        elif trigger in (
            InboxEventType.environment_changed,
            InboxEventType.attachment_added,
        ):
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))

        elif trigger == InboxEventType.priority_changed:
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))
            if issue.reporter_id:
                recipients.add(str(issue.reporter_id))
            # Matrix has triage: True — include release triage lead
            leads = await self._triage_recipients(db, issue)
            recipients.update(str(u.id) for u in leads)

        elif trigger in (
            InboxEventType.needs_info_replied,
            InboxEventType.moved_into_project,
            InboxEventType.recurrence_on_cancelled,
        ):
            # moved_into_project: issue.project_id is already the new project.
            leads = await self._triage_recipients(db, issue)
            recipients.update(str(u.id) for u in leads)

        elif trigger in ASSIGNEE_EVENTS:
            if issue.assignee_id:
                recipients.add(str(issue.assignee_id))

        elif trigger in SUPPORT_EVENTS:
            from app.services.subscriber_service import subscriber_ids

            ids = await subscriber_ids(db, issue.id)
            if ids:
                result = await db.execute(
                    select(User.id).where(User.id.in_(ids), User.role == UserRole.support)
                )
                recipients.update(str(uid) for uid in result.scalars().all())

        # Remove the actor — they don't get notified of their own actions,
        # then re-add any forced recipients (e.g. self-assignment).
        actor_id = actor.id if actor is not None else None
        logger.info("[fan_out] trigger=%s recipients_before_discard=%s actor_id=%s", trigger, recipients, actor_id)
        recipients.discard(str(actor_id))
        recipients.update(forced_recipients)
        if suppress_user_ids:
            recipients -= suppress_user_ids
        recipients = await self._drop_invisible(db, recipients, issue, timeline_event, trigger)
        logger.info("[fan_out] trigger=%s final_recipients=%s", trigger, recipients)

        # ── Create InboxItem rows ─────────────────────────────────────────────
        items: list[InboxItem] = []
        for user_id_str in recipients:
            item = InboxItem(
                user_id=int(user_id_str),
                actor_id=actor_id,
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

        # ── Dispatch Telegram notifications (best-effort) ─────────────────────
        # Reactions reach Telegram only for the comment's author; mentioned
        # users and the assignee get the inbox item and nothing more.
        telegram_only: set[int] | None = None
        if trigger == InboxEventType.reaction:
            telegram_only = (
                {timeline_event.actor_id}
                if timeline_event is not None and timeline_event.actor_id
                else set()
            )

        await self._dispatch_telegram(
            db, trigger, issue, actor, items, meta,
            telegram_only=telegram_only,
            delay_seconds=delay_seconds,
        )

        return items

    async def fan_out_release(
        self,
        db: AsyncSession,
        trigger: InboxEventType,
        release,
        actor: User | None,
        recipient_ids: set[int],
        meta: dict[str, Any] | None = None,
        roles: dict[int, set[str]] | None = None,
    ) -> list[InboxItem]:
        """The release-scoped variant of ``fan_out`` (slice 09): one ``InboxItem``
        per recipient with ``issue_id`` null and ``release_id`` set.

        The caller computes the audience; the actor is dropped and so is anyone
        who isn't an active tech user (a release has no Support-visible content).
        ``roles`` maps a recipient to their matrix relationships for this event
        (``assignee`` / ``cto``) — Telegram is sent when the matrix row switches
        one of them on.
        """
        from app.policy import is_tech

        ids = set(recipient_ids)
        if actor is not None:
            ids.discard(actor.id)
        if not ids:
            return []
        users = (await db.execute(
            select(User).where(User.id.in_(ids), User.is_active.is_(True))
        )).scalars().all()
        users = [u for u in users if is_tech(u.role)]

        items: list[InboxItem] = []
        for u in users:
            item = InboxItem(
                user_id=u.id,
                actor_id=actor.id if actor is not None else None,
                issue_id=None,
                release_id=release.id,
                event_type=trigger,
                is_read=False,
                meta=meta,
            )
            db.add(item)
            items.append(item)
        await db.flush()

        try:
            from app.core.redis_client import publish

            for item in items:
                await publish(f"rw:inbox:{item.user_id}", {
                    "type": "inbox_item", "event_type": trigger.value,
                    "issue_id": None, "release_id": str(release.id), "item_id": str(item.id),
                })
        except Exception:
            pass

        await self._dispatch_release_telegram(
            db, trigger, release, actor, items, {u.id: u for u in users}, meta or {}, roles or {},
        )
        return items

    async def _dispatch_release_telegram(
        self, db, trigger, release, actor, items, users_by_id, meta, roles,
    ) -> None:
        """Telegram for a release-only notice — same matrix, same outbox as items."""
        if not items:
            return
        try:
            from sqlalchemy.orm import attributes as sa_attrs

            from app.config import settings as app_settings
            from app.db.models.project import Project
            from app.db.models.system_setting import SystemSetting
            from app.db.models.telegram_integration import TelegramIntegration
            from app.tasks.notifications import send_telegram_notification
            from app.telegram.templates import MESSAGE_TEMPLATES

            setting = (await db.execute(
                select(SystemSetting).where(
                    SystemSetting.category == "notifications", SystemSetting.key == "matrix",
                )
            )).scalar_one_or_none()
            row = resolve_matrix(setting.value if setting else None).get(trigger.value)
            if not row or trigger.value not in MESSAGE_TEMPLATES:
                return
            tg_cfg = (await db.execute(
                select(SystemSetting).where(
                    SystemSetting.category == "telegram", SystemSetting.key == "config",
                )
            )).scalar_one_or_none()
            bot_token = (tg_cfg.value or {}).get("bot_token") if tg_cfg else None
            if not bot_token:
                return
            proxy_cfg = (await db.execute(
                select(SystemSetting).where(
                    SystemSetting.category == "proxy", SystemSetting.key == "config",
                    SystemSetting.is_active.is_(True),
                )
            )).scalar_one_or_none()
            proxy_url = None
            if proxy_cfg and (proxy_cfg.value or {}).get("enabled"):
                proxy_url = proxy_cfg.value.get("http") or proxy_cfg.value.get("https") or None

            tg_by_user = {
                t.user_id: t for t in (await db.execute(
                    select(TelegramIntegration).where(
                        TelegramIntegration.user_id.in_([i.user_id for i in items]),
                        TelegramIntegration.is_active.is_(True),
                    )
                )).scalars().all()
            }
            project = await db.get(Project, release.project_id)
            frontend_base = (
                ((tg_cfg.value or {}).get("frontend_url") if tg_cfg else None)
                or app_settings.FRONTEND_URL
            ).rstrip("/")

            def _esc(v: object) -> str:
                return html_lib.escape(str(v)) if v is not None else ""

            context = {
                "release_name": _esc(release.version),
                "release_url": f"{frontend_base}/releases/{release.id}",
                "project_name": _esc(project.name if project else ""),
                "release_deadline": _esc(
                    release.target_date.strftime("%b %d, %Y") if release.target_date else "—"
                ),
                "actor": _esc((actor.name or actor.username) if actor else "Releasewatch"),
                "moved_count": _esc(meta.get("moved", 0)),
            }
            for item in items:
                tg = tg_by_user.get(item.user_id)
                if tg is None:
                    continue
                user = users_by_id.get(item.user_id)
                rel = set(roles.get(item.user_id, set()))
                if user is not None and getattr(user.role, "value", user.role) in ("cto", "admin"):
                    rel.add("cto")
                if not any(row.get(r) for r in rel):
                    item.telegram_status = "skipped"
                    continue
                item_meta = dict(item.meta or {})
                item_meta["tg_context"] = context
                item_meta["tg_template"] = trigger.value
                send_token = uuid4().hex
                item_meta["send_token"] = send_token
                item.meta = item_meta
                sa_attrs.flag_modified(item, "meta")
                item.telegram_status = "pending"
                send_telegram_notification.apply_async(
                    args=[tg.chat_id, trigger.value, context],
                    kwargs={
                        "bot_token": bot_token, "proxy_url": proxy_url,
                        "inbox_item_id": item.id, "send_token": send_token,
                    },
                    countdown=2,
                    queue="notifications",
                )
        except Exception:
            logger.warning("Telegram dispatch skipped (best-effort)", exc_info=True)

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _dispatch_telegram(
        self,
        db: AsyncSession,
        trigger: InboxEventType,
        issue: Issue,
        actor: User,
        items: list[InboxItem],
        meta: dict[str, Any] | None = None,
        telegram_only: set[int] | None = None,
        delay_seconds: int = 0,
    ) -> None:
        """Send Telegram notifications based on the stored notification matrix.

        For each inbox item recipient, checks whether their relationship to the
        issue (reporter/assignee) or project designation (triage_lead/cto) appears in the
        matrix row for this event. Dispatches a Celery task per eligible recipient
        who has a linked Telegram account. Failures are swallowed — this is
        best-effort, same as the Redis push above.
        """
        if not items:
            return
        try:
            from app.db.models.release import Release
            from app.db.models.project import Project
            from app.db.models.system_setting import SystemSetting
            from app.db.models.telegram_integration import TelegramIntegration
            from app.config import settings as app_settings
            from app.services.project_service import project_needs_triage_lead

            # Load persisted matrix and overlay on defaults so notifications fire
            # out-of-the-box before an admin has explicitly saved settings.
            result = await db.execute(
                select(SystemSetting)
                .where(SystemSetting.category == "notifications")
                .where(SystemSetting.key == "matrix")
            )
            setting = result.scalar_one_or_none()
            matrix = resolve_matrix(setting.value if setting else None)

            event_key = trigger.value
            row = matrix.get(event_key)
            # Reactions bypass the matrix entirely: fan_out already computed the
            # exact audience (comment author / mentioned / assignee), and those
            # relationships have no matrix role, so re-gating would drop them all.
            is_reaction = event_key == InboxEventType.reaction.value
            if not row and not is_reaction:
                return

            user_ids = [item.user_id for item in items]

            users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
            users_by_id: dict[int, User] = {u.id: u for u in users_result.scalars().all()}

            tg_result = await db.execute(
                select(TelegramIntegration)
                .where(TelegramIntegration.user_id.in_(user_ids))
                .where(TelegramIntegration.is_active.is_(True))
            )
            tg_by_user: dict[int, TelegramIntegration] = {
                t.user_id: t for t in tg_result.scalars().all()
            }

            # Load real bot token from DB — the env var may be a placeholder.
            tg_cfg_result = await db.execute(
                select(SystemSetting)
                .where(SystemSetting.category == "telegram")
                .where(SystemSetting.key == "config")
            )
            tg_cfg_setting = tg_cfg_result.scalar_one_or_none()
            bot_token: str | None = (
                (tg_cfg_setting.value or {}).get("bot_token") if tg_cfg_setting else None
            )
            if not bot_token:
                logger.warning("Telegram dispatch skipped: no bot token in DB settings")
                return

            # Load proxy from DB so the Celery worker can route through it.
            proxy_cfg_result = await db.execute(
                select(SystemSetting)
                .where(SystemSetting.category == "proxy")
                .where(SystemSetting.key == "config")
                .where(SystemSetting.is_active.is_(True))
            )
            proxy_cfg_setting = proxy_cfg_result.scalar_one_or_none()
            proxy_url: str | None = None
            if proxy_cfg_setting and (proxy_cfg_setting.value or {}).get("enabled"):
                proxy_url = (
                    proxy_cfg_setting.value.get("http")
                    or proxy_cfg_setting.value.get("https")
                    or None
                )

            # Load release and project for enriched notification context.
            release_result = await db.execute(select(Release).where(Release.id == issue.release_id))
            release = release_result.scalar_one_or_none()
            project_result = await db.execute(select(Project).where(Project.id == issue.project_id))
            project = project_result.scalar_one_or_none()

            needs_lead = project is not None and await project_needs_triage_lead(db, project)

            subscribers: set[int] = set()
            if row and row.get("subscriber"):
                from app.services.subscriber_service import subscriber_ids

                subscribers = await subscriber_ids(db, issue.id)

            project_name = project.name if project else "Unknown Project"
            release_name = release.version if release else "Unknown Release"
            release_deadline = (
                release.target_date.strftime("%b %d, %Y")
                if release and release.target_date
                else "No deadline set"
            )

            tg_frontend_url = (tg_cfg_setting.value or {}).get("frontend_url") if tg_cfg_setting else None
            frontend_base = (tg_frontend_url or app_settings.FRONTEND_URL).rstrip("/")
            issue_slug = f"issue-{issue.issue_number}"
            issue_url = f"{frontend_base}/issue/{issue_slug}"

            # Build direct comment URL when a timeline event is linked.
            timeline_id = items[0].timeline_id if items else None
            comment_url = (
                f"{frontend_base}/issue/{issue_slug}#comment-{timeline_id}"
                if timeline_id
                else issue_url
            )

            _meta = meta or {}
            from_val = _meta.get("from", "—")
            to_val = _meta.get("to", "—")

            actor_name = (actor.name or actor.username) if actor is not None else "Releasewatch"
            actor_url = (
                f"{frontend_base}/u/{actor.username}" if actor is not None and actor.username
                else f"{frontend_base}/team"
            )

            def _esc(v: object) -> str:
                return html_lib.escape(str(v)) if v is not None else ""

            priority_val = getattr(issue.priority, "value", issue.priority) or "unrated"
            context = {
                "issue_number": issue.issue_number,
                "title": _esc(issue.title),
                "issue_url": issue_url,
                "comment_url": comment_url,
                "actor": _esc(actor_name),
                "actor_url": actor_url,
                "priority": _esc(priority_val),
                "excerpt": _esc(_meta.get("body_snippet", "")),
                "emoji": _meta.get("emoji", ""),
                "project_name": _esc(project_name),
                "release_name": _esc(release_name),
                "release_deadline": _esc(release_deadline),
                # Transition fields — each template uses the pair relevant to its event type.
                "old_status": _esc(from_val),
                "new_status": _esc(to_val),
                "old_environment": _esc(from_val),
                "new_environment": _esc(to_val),
                "old_release": _esc(from_val),
                "new_release": _esc(to_val),
                "old_priority": _esc(from_val or "unrated"),
                "new_priority": _esc(to_val or "unrated"),
                "old_project": _esc(from_val),
                "new_project": _esc(to_val),
                # support_cancelled (slice 06): the human-readable reason, or
                # where a merged report went.
                "cancel_reason": _esc(_meta.get("reason_label", "")),
                # item_returned (08a): where the problem was caught.
                "return_reason": _esc(_meta.get("reason_label", "")),
                "merged_into_key": _esc(_meta.get("merged_into_key", "")),
                # queue_changed / due_soon / overdue (slice 10).
                "queue_action": _esc({"reorder": "moved", "pin": "pinned", "unpin": "unpinned"}
                                     .get(_meta.get("action"), _meta.get("action", ""))),
                "old_index": _esc(_meta.get("old_index", "—")),
                "new_index": _esc(_meta.get("new_index", "—")),
                "due_date": _esc(_meta.get("due_date", "")),
                "queue_url": f"{frontend_base}/my-work",
                "merged_into_url": (
                    f"{frontend_base}/issue/issue-{_meta['merged_into_number']}"
                    if _meta.get("merged_into_number") else issue_url
                ),
            }

            from app.telegram.templates import MESSAGE_TEMPLATES
            from app.tasks.notifications import send_telegram_notification
            from sqlalchemy.orm import attributes as sa_attrs

            # Events without a template can't be delivered — skip the whole batch.
            # A support report's ``filed`` notice uses Support copy (slice 05).
            template_key = event_key
            if (
                trigger == InboxEventType.filed
                and getattr(issue.source, "value", issue.source) == IssueSource.support.value
            ):
                template_key = "support_report_filed"
            elif trigger == InboxEventType.support_cancelled and _meta.get("merged_into_key"):
                template_key = "support_merged"
            if template_key not in MESSAGE_TEMPLATES:
                logger.warning("No Telegram template for event: %s", template_key)
                return

            for item in items:
                user = users_by_id.get(item.user_id)
                tg = tg_by_user.get(item.user_id)
                if not user or not tg:
                    # No Telegram account linked — leave telegram_status NULL
                    continue

                # Restricted audience (reactions): everyone else is inbox-only.
                if telegram_only is not None and user.id not in telegram_only:
                    item.telegram_status = "skipped"
                    continue

                is_project_triage_lead = project is not None and (
                    project.triage_lead_id == user.id
                    # AC-23: admins stand in while the project has no active lead.
                    or (needs_lead and user.role == UserRole.admin)
                )
                should_notify = is_reaction or (
                    (row.get("reporter") and issue.reporter_id == user.id)
                    or (row.get("assignee") and issue.assignee_id == user.id)
                    or (row.get("triage") and is_project_triage_lead)
                    or (row.get("cto") and user.role in (UserRole.cto, UserRole.admin))
                    or (row.get("subscriber") and user.id in subscribers)
                )
                if not should_notify:
                    item.telegram_status = "skipped"
                    continue

                # Persist delivery intent and rendered context BEFORE enqueuing.
                # This ensures the beat task can retry even if Redis/Celery are
                # unavailable at the moment of the event.
                item_meta = dict(item.meta or {})
                item_meta["tg_context"] = context
                item_meta["tg_template"] = template_key
                # Identifies this specific scheduled send. If the item is later
                # refreshed (the actor swapped emoji), the token is rotated and
                # the already-queued task retires itself instead of delivering
                # a stale message.
                send_token = uuid4().hex
                item_meta["send_token"] = send_token
                item.meta = item_meta
                sa_attrs.flag_modified(item, "meta")
                item.telegram_status = "pending"

                # countdown=2 gives the HTTP request's transaction time to commit
                # before the worker reads the inbox item by ID. A larger
                # delay_seconds additionally holds the send open for undo, and is
                # mirrored onto telegram_next_retry_at so the beat task doesn't
                # deliver it early.
                countdown = max(delay_seconds, 2)
                if delay_seconds:
                    item.telegram_next_retry_at = datetime.now(timezone.utc) + timedelta(
                        seconds=delay_seconds
                    )

                send_telegram_notification.apply_async(
                    args=[tg.chat_id, template_key, context],
                    kwargs={
                        "bot_token": bot_token,
                        "proxy_url": proxy_url,
                        "inbox_item_id": item.id,
                        "send_token": send_token,
                    },
                    countdown=countdown,
                    queue="notifications",
                )
        except Exception:
            logger.warning("Telegram dispatch skipped (best-effort)", exc_info=True)

    @staticmethod
    async def requeue_telegram(
        db: AsyncSession, item: InboxItem, send_token: str, delay_seconds: int
    ) -> None:
        """Re-schedule an already-pending item's Telegram send with a new token.

        Used when a reaction notice is rewritten in place: the caller has
        already rotated ``meta['send_token']``, so the previously queued task
        will no-op and this one delivers the current content instead.
        """
        try:
            from app.db.models.system_setting import SystemSetting
            from app.db.models.telegram_integration import TelegramIntegration
            from app.tasks.notifications import send_telegram_notification

            tg = (await db.execute(
                select(TelegramIntegration)
                .where(TelegramIntegration.user_id == item.user_id)
                .where(TelegramIntegration.is_active.is_(True))
            )).scalar_one_or_none()
            if tg is None:
                return

            cfg = (await db.execute(
                select(SystemSetting)
                .where(SystemSetting.category == "telegram")
                .where(SystemSetting.key == "config")
            )).scalar_one_or_none()
            bot_token = (cfg.value or {}).get("bot_token") if cfg else None
            if not bot_token:
                return

            proxy_cfg = (await db.execute(
                select(SystemSetting)
                .where(SystemSetting.category == "proxy")
                .where(SystemSetting.key == "config")
                .where(SystemSetting.is_active.is_(True))
            )).scalar_one_or_none()
            proxy_url = None
            if proxy_cfg and (proxy_cfg.value or {}).get("enabled"):
                proxy_url = (
                    proxy_cfg.value.get("http") or proxy_cfg.value.get("https") or None
                )

            send_telegram_notification.apply_async(
                args=[
                    tg.chat_id,
                    (item.meta or {}).get("tg_template", item.event_type),
                    (item.meta or {}).get("tg_context", {}),
                ],
                kwargs={
                    "bot_token": bot_token,
                    "proxy_url": proxy_url,
                    "inbox_item_id": item.id,
                    "send_token": send_token,
                },
                countdown=max(delay_seconds, 2),
                queue="notifications",
            )
        except Exception:
            # Best-effort, same as the main dispatch path: the beat task will
            # still pick the item up once its retry clock elapses.
            logger.warning("Telegram requeue skipped (best-effort)", exc_info=True)

    @staticmethod
    async def _drop_invisible(
        db: AsyncSession,
        recipients: set[str],
        issue: Issue,
        timeline_event: IssueTimeline | None,
        trigger: InboxEventType | None = None,
    ) -> set[str]:
        """Keep only recipients who may see ``issue`` (and the note, if it's internal).

        Support users keep only the three ``support_*`` events and mentions
        (slice 06) — never comments, status changes, or anything else.
        """
        from app.policy import Action, allows, is_tech
        from app.services.authz import actor_of, issue_target

        if not recipients:
            return recipients
        result = await db.execute(select(User).where(User.id.in_([int(r) for r in recipients])))
        target = issue_target(issue)
        internal = timeline_event is not None and timeline_event.is_internal
        support_may_receive = trigger in SUPPORT_RECEIVABLE
        return {
            str(u.id)
            for u in result.scalars().all()
            if allows(actor_of(u), Action.view_item, target)
            and (not internal or is_tech(u.role))
            and (support_may_receive or is_tech(u.role))
        }

    async def _triage_recipients(self, db: AsyncSession, issue: Issue) -> list[User]:
        """Return the project's triage lead — or every active admin when the
        project needs one (lead unset or deactivated, AC-23)."""
        from app.db.models.project import Project

        if issue.project_id:
            proj_result = await db.execute(
                select(Project).where(Project.id == issue.project_id)
            )
            project = proj_result.scalar_one_or_none()
            if project and project.triage_lead_id:
                tl_result = await db.execute(
                    select(User).where(
                        User.id == project.triage_lead_id,
                        User.is_active.is_(True),
                    )
                )
                tl = tl_result.scalar_one_or_none()
                if tl:
                    return [tl]
            if project is not None:
                return await self._users_with_role(db, UserRole.admin)

        return []

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
                    f"rw:inbox:{item.user_id}",
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
