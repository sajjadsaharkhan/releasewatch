"""Support channel — the per-project Telegram topic (slice 21, PRD v3.1 §8.11, FR-70/71).

``record`` is the one writer of the outbox (``support_channel_posts``), called
from the services that own each event. It does nothing for a project without an
enabled channel or for an internal item, and it never raises into its caller:
a post never blocks or undoes an action (BR-72). It reads only what the caller
hands it — the public comment an action wrote — so an internal note cannot
reach a post by construction (BR-31).
"""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings as app_settings
from app.core.clock import utcnow
from app.core.errors import DomainError
from app.db.models.issue import Issue, IssueSource, issue_key
from app.db.models.project import Project
from app.db.models.support_channel_post import SupportChannelPost
from app.db.models.system_setting import SystemSetting
from app.db.models.telegram_integration import TelegramIntegration
from app.db.models.user import User
from app.telegram.client import TelegramAPIError, TelegramClient

logger = logging.getLogger(__name__)

#: One item's changes inside this window are one post (FR-71).
ITEM_WINDOW = timedelta(seconds=60)
#: A batch (On production, a ship) is sent this long after its first item.
BATCH_DELAY = timedelta(seconds=5)

KINDS = ("new_report", "status", "return_requested", "return_confirmed", "return_dismissed")


class SupportChannelService:
    # ── Settings (FR-70) ──────────────────────────────────────────────────────

    async def get_project(self, db: AsyncSession, project_id: int) -> Project:
        project = await db.get(Project, project_id)
        if project is None:
            raise DomainError(404, "Project not found.", "not_found")
        return project

    async def state(self, db: AsyncSession, project: Project) -> dict[str, Any]:
        counts = dict((await db.execute(
            select(SupportChannelPost.status, func.count())
            .where(SupportChannelPost.project_id == project.id)
            .group_by(SupportChannelPost.status)
        )).all())
        last_error = (await db.execute(
            select(SupportChannelPost.last_error)
            .where(
                SupportChannelPost.project_id == project.id,
                SupportChannelPost.last_error.is_not(None),
                SupportChannelPost.status != "sent",
            )
            .order_by(SupportChannelPost.id.desc()).limit(1)
        )).scalar_one_or_none()
        return {
            "chat_id": project.support_chat_id,
            "thread_id": project.support_thread_id,
            "enabled": bool(project.support_channel_enabled),
            "tested": project.support_channel_tested_at is not None,
            "tested_at": project.support_channel_tested_at,
            "pending_posts": counts.get("pending", 0),
            "failed_posts": counts.get("failed", 0),
            "last_error": last_error,
        }

    async def save(
        self, db: AsyncSession, project: Project, chat_id: int,
        thread_id: int | None, enabled: bool,
    ) -> Project:
        """Save the channel. A new chat or topic clears the test, and enabling needs a
        test passed since the last such change (409 ``support_channel_untested``)."""
        moved = chat_id != project.support_chat_id or thread_id != project.support_thread_id
        tested = project.support_channel_tested_at is not None and not moved
        if enabled and not tested:
            raise DomainError(
                409, "Send a test message to this chat and topic before enabling the channel.",
                "support_channel_untested",
            )
        project.support_chat_id = chat_id
        project.support_thread_id = thread_id
        project.support_channel_enabled = enabled
        if moved:
            project.support_channel_tested_at = None
        db.add(project)
        await db.flush()
        return project

    async def send_test(self, db: AsyncSession, project: Project) -> dict[str, Any]:
        """Post a test message; ``{ok, error?}`` carries Telegram's own description."""
        from app.telegram.config import load_runtime

        if project.support_chat_id is None:
            return {"ok": False, "error": "Save a chat ID first."}
        token, proxy_url = await load_runtime(db)
        if not token:
            return {"ok": False, "error": "The Telegram bot is not configured."}
        client = TelegramClient(token=token, proxy_url=proxy_url)
        try:
            await client.send_message(
                chat_id=project.support_chat_id,
                text=f"Releasewatch test message for {_esc(project.name)}",
                message_thread_id=project.support_thread_id,
            )
        except TelegramAPIError as exc:
            return {"ok": False, "error": str(exc).removeprefix("sendMessage failed: ")}
        except Exception as exc:  # network, proxy, timeout
            logger.warning("Support channel test message failed: %s", exc)
            return {"ok": False, "error": f"Could not reach Telegram ({type(exc).__name__})."}
        finally:
            await client.close()
        project.support_channel_tested_at = utcnow()
        db.add(project)
        await db.flush()
        return {"ok": True}

    # ── Events → outbox (FR-71) ───────────────────────────────────────────────

    async def record(
        self,
        db: AsyncSession,
        issue: Issue,
        kind: str,
        meta: dict[str, Any] | None = None,
        batch_id: str | None = None,
    ) -> None:
        """Queue a post about ``issue``. ``meta``: ``from`` / ``to`` / ``reason`` /
        ``text`` (public text only) for a status change; ``text`` for return events."""
        if getattr(issue.source, "value", issue.source) != IssueSource.support.value:
            return
        try:
            project = await db.get(Project, issue.project_id)
            if (
                project is None or not project.support_channel_enabled
                or project.support_chat_id is None
            ):
                return
            async with db.begin_nested():
                await self._record(db, project, issue, kind, meta or {}, batch_id)
        except Exception:
            logger.warning(
                "Support channel post for issue %s was not recorded", issue.id, exc_info=True,
            )

    async def _record(
        self, db: AsyncSession, project: Project, issue: Issue, kind: str, meta: dict,
        batch_id: str | None,
    ) -> None:
        now = utcnow()
        to_status = meta.get("to")
        if kind == "status" and meta.get("from") == to_status:
            return
        payload = await self._payload(db, project, issue, meta)

        if kind == "status" and batch_id:
            await self._add_to_batch(db, project, issue, meta, payload, batch_id, now)
            return

        if kind == "status":
            existing = (await db.execute(
                select(SupportChannelPost).where(
                    SupportChannelPost.issue_id == issue.id,
                    SupportChannelPost.kind == "status",
                    SupportChannelPost.batch_id.is_(None),
                    SupportChannelPost.status == "pending",
                    SupportChannelPost.attempts == 0,
                    SupportChannelPost.not_before > now,
                ).order_by(SupportChannelPost.id.desc()).limit(1).with_for_update()
            )).scalar_one_or_none()
            if existing is not None:
                existing.last_status = to_status
                existing.payload = {
                    **payload, "text": payload.get("text") or existing.payload.get("text"),
                }
                db.add(existing)
                await db.flush()
                return

        db.add(SupportChannelPost(
            project_id=project.id, issue_id=issue.id, kind=kind,
            first_status=meta.get("from") if kind == "status" else None,
            last_status=to_status if kind == "status" else None,
            payload=payload,
            not_before=now + ITEM_WINDOW if kind == "status" else now,
        ))
        await db.flush()

    async def _add_to_batch(
        self, db: AsyncSession, project: Project, issue: Issue, meta: dict, payload: dict,
        batch_id: str, now,
    ) -> None:
        line = {
            "key": payload["key"], "title": payload["title"], "url": payload["url"],
            "from": meta.get("from"), "to": meta.get("to"),
        }
        row = (await db.execute(
            select(SupportChannelPost).where(
                SupportChannelPost.project_id == project.id,
                SupportChannelPost.batch_id == batch_id,
            ).with_for_update()
        )).scalar_one_or_none()
        if row is not None:
            row.payload = {**row.payload, "items": [*row.payload.get("items", []), line]}
            db.add(row)
        else:
            title = "On production"
            if meta.get("reason") == "ship":
                from app.db.models.release import Release

                release = await db.get(Release, issue.release_id) if issue.release_id else None
                title = f"Released {release.version}" if release is not None else "Released"
            db.add(SupportChannelPost(
                project_id=project.id, batch_id=batch_id, kind="batch",
                payload={"project_name": project.name, "title": title, "items": [line]},
                not_before=now + BATCH_DELAY,
            ))
        await db.flush()

    async def _payload(
        self, db: AsyncSession, project: Project, issue: Issue, meta: dict,
    ) -> dict[str, Any]:
        base = await self._frontend_base(db)
        key = issue_key(issue.type, issue.issue_number)
        reporter = None
        if issue.reporter_id:
            user = await db.get(User, issue.reporter_id)
            tg = (await db.execute(
                select(TelegramIntegration.telegram_username).where(
                    TelegramIntegration.user_id == issue.reporter_id,
                    TelegramIntegration.is_active.is_(True),
                )
            )).scalar_one_or_none()
            if user is not None:
                reporter = {"name": user.name or user.username, "username": tg or None}
        return {
            "key": key, "title": issue.title, "project_name": project.name,
            "url": f"{base}/issue/{key.lower()}", "reporter": reporter,
            "text": (meta.get("text") or "").strip() or None,
        }

    @staticmethod
    async def _frontend_base(db: AsyncSession) -> str:
        row = (await db.execute(
            select(SystemSetting).where(
                SystemSetting.category == "telegram", SystemSetting.key == "config",
                SystemSetting.is_active.is_(True),
            )
        )).scalar_one_or_none()
        configured = (row.value or {}).get("frontend_url") if row else None
        return (configured or app_settings.FRONTEND_URL).rstrip("/")


def _esc(value: str) -> str:
    import html

    return html.escape(value)


support_channel_service = SupportChannelService()
