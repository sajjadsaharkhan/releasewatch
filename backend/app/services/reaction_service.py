"""ReactionService — emoji reactions on timeline comments.

Reactions live outside the append-only timeline log: reacting never writes an
``IssueTimeline`` row, so the audit trail stays signal.  Only ``comment`` events
can be reacted to, matching the restriction ``edit_comment`` / ``delete_comment``
already enforce.
"""

from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes as sa_attrs

from app.core.reactions import (
    ALLOWED_REACTIONS,
    REACTION_EMOJI,
    REACTION_TELEGRAM_DELAY,
)
from app.db.models.comment_reaction import CommentReaction
from app.db.models.inbox_item import InboxEventType, InboxItem
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.user import User


class ReactionService:
    """Adds, removes and summarises comment reactions."""

    # ── Validation ────────────────────────────────────────────────────────────

    @staticmethod
    def _validate_key(emoji_key: str) -> None:
        if emoji_key not in ALLOWED_REACTIONS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unsupported reaction '{emoji_key}'.",
            )

    @staticmethod
    async def _load_comment(
        db: AsyncSession, issue_id: int, timeline_id: int
    ) -> IssueTimeline:
        """Return the target event, or raise if it isn't a comment on this issue."""
        result = await db.execute(
            select(IssueTimeline).where(
                IssueTimeline.id == timeline_id,
                IssueTimeline.issue_id == issue_id,
            )
        )
        event = result.scalar_one_or_none()
        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Timeline event not found",
            )
        if event.event_type != TimelineEventType.comment:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only comments can be reacted to.",
            )
        return event

    # ── Mutations ─────────────────────────────────────────────────────────────

    async def add(
        self,
        db: AsyncSession,
        issue_id: int,
        timeline_id: int,
        user: User,
        emoji_key: str,
    ) -> tuple[IssueTimeline, int | None, bool]:
        """Set this user's reaction on a comment.

        Reactions are mutually exclusive, so this is an upsert on
        ``uq_comment_reaction_user``: picking a different emoji rewrites the
        existing row rather than adding a second one.

        Returns ``(comment_event, reaction_id, changed)``.  ``changed`` is
        ``False`` when the user already held this exact emoji — the ``where``
        clause makes that a no-op, so a double-click fires no notification.
        """
        self._validate_key(emoji_key)
        event = await self._load_comment(db, issue_id, timeline_id)

        now = datetime.now(tz=timezone.utc)
        stmt = (
            pg_insert(CommentReaction)
            .values(
                timeline_id=timeline_id,
                user_id=user.id,
                emoji_key=emoji_key,
                created_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_comment_reaction_user",
                set_={"emoji_key": emoji_key, "created_at": now},
                # Re-clicking the same emoji changes nothing and returns no row.
                where=CommentReaction.emoji_key != emoji_key,
            )
            .returning(CommentReaction.id)
        )
        result = await db.execute(stmt)
        reaction_id = result.scalar_one_or_none()
        await db.flush()
        return event, reaction_id, reaction_id is not None

    async def remove(
        self,
        db: AsyncSession,
        issue_id: int,
        timeline_id: int,
        user: User,
        emoji_key: str,
    ) -> None:
        """Remove a reaction. Silent no-op when it was never there."""
        self._validate_key(emoji_key)
        await self._load_comment(db, issue_id, timeline_id)

        result = await db.execute(
            delete(CommentReaction).where(
                CommentReaction.timeline_id == timeline_id,
                CommentReaction.user_id == user.id,
                CommentReaction.emoji_key == emoji_key,
            )
        )
        await db.flush()

        # Only cancel when something was actually removed. Deleting an emoji the
        # user no longer holds (they already switched to another) must not
        # retract the notice for the reaction they *do* hold.
        if result.rowcount:
            await self.cancel_pending_notification(db, timeline_id, user.id)

    # ── Notification lifecycle ────────────────────────────────────────────────

    @staticmethod
    async def cancel_pending_notification(
        db: AsyncSession, timeline_id: int, actor_id: int
    ) -> int:
        """Drop this actor's undelivered reaction notices for a comment.

        Called when a reaction is removed: a notice about a reaction that no
        longer exists is noise.  Items already delivered to Telegram are left
        alone — that bell cannot be unrung — and so are ones the recipient has
        already read.
        """
        result = await db.execute(
            select(InboxItem).where(
                InboxItem.timeline_id == timeline_id,
                InboxItem.actor_id == actor_id,
                InboxItem.event_type == InboxEventType.reaction,
                InboxItem.is_read.is_(False),
            )
        )
        removed = 0
        for item in result.scalars().all():
            if item.telegram_status == "sent":
                continue
            await db.delete(item)
            removed += 1
        await db.flush()
        return removed

    async def sync_reaction_notification(
        self,
        db: AsyncSession,
        issue,
        actor: User,
        event: IssueTimeline,
        emoji_key: str,
        reaction_id: int,
    ) -> None:
        """Create or refresh the inbox/Telegram notice for a reaction.

        When this actor already has an undelivered notice on this comment (they
        just switched emoji), it is rewritten in place and the send clock is
        restarted, so the recipient gets exactly one notification reflecting the
        final choice.  Otherwise the normal fan-out runs.
        """
        from app.services.inbox_service import inbox_service

        emoji = REACTION_EMOJI.get(emoji_key, "")
        now = datetime.now(tz=timezone.utc)

        result = await db.execute(
            select(InboxItem).where(
                InboxItem.timeline_id == event.id,
                InboxItem.actor_id == actor.id,
                InboxItem.event_type == InboxEventType.reaction,
                InboxItem.is_read.is_(False),
            )
        )
        existing = [i for i in result.scalars().all() if i.telegram_status != "sent"]

        if existing:
            for item in existing:
                meta = dict(item.meta or {})
                meta["reaction_id"] = reaction_id
                meta["emoji"] = emoji
                if ctx := meta.get("tg_context"):
                    meta["tg_context"] = {**ctx, "emoji": emoji}
                # A fresh token retires whatever task is already queued for this
                # item, so the superseded emoji is never delivered.
                token = uuid4().hex
                meta["send_token"] = token
                item.meta = meta
                sa_attrs.flag_modified(item, "meta")

                if item.telegram_status == "pending":
                    item.telegram_next_retry_at = now + timedelta(
                        seconds=REACTION_TELEGRAM_DELAY
                    )
                    await self._enqueue_delayed(db, item, token)
            await db.flush()
            return

        body = event.body or ""
        body_snippet = (body[:200] + "…") if len(body) > 200 else (body or None)

        # Collapse: skip recipients already sitting on an unread reaction notice
        # for this comment (from any actor) so a busy thread doesn't spam them.
        already = await db.execute(
            select(InboxItem.user_id).where(
                InboxItem.timeline_id == event.id,
                InboxItem.event_type == InboxEventType.reaction,
                InboxItem.is_read.is_(False),
            )
        )
        suppress = {str(uid) for uid in already.scalars().all()}

        await inbox_service.fan_out(
            db=db,
            trigger=InboxEventType.reaction,
            issue=issue,
            actor=actor,
            timeline_event=event,
            meta={
                "emoji": emoji,
                "body_snippet": body_snippet,
                "reaction_id": reaction_id,
            },
            suppress_user_ids=suppress,
            delay_seconds=REACTION_TELEGRAM_DELAY,
        )

    @staticmethod
    async def _enqueue_delayed(db: AsyncSession, item: InboxItem, token: str) -> None:
        """Re-queue a refreshed reaction notice with a full delay window."""
        from app.services.inbox_service import inbox_service

        await inbox_service.requeue_telegram(db, item, token, REACTION_TELEGRAM_DELAY)

    @staticmethod
    async def reaction_notification_still_valid(
        db: AsyncSession, item: InboxItem
    ) -> bool:
        """True when a reaction notice should still be delivered.

        False once the underlying reaction has been removed — which is how the
        delay window turns into a cancellation.
        """
        if item.event_type != InboxEventType.reaction:
            return True
        reaction_id = (item.meta or {}).get("reaction_id")
        if reaction_id is None:
            return True  # created before reaction_id was tracked; let it through
        found = await db.execute(
            select(CommentReaction.id).where(CommentReaction.id == reaction_id)
        )
        return found.scalar_one_or_none() is not None

    # ── Read ──────────────────────────────────────────────────────────────────

    @staticmethod
    def summarize(event: IssueTimeline, current_user_id: int | None) -> list[dict]:
        """Group an event's eager-loaded reactions into per-emoji summaries.

        Ordered by ``ALLOWED_REACTIONS`` so pill order is stable across clients
        and across re-renders.  Relies on ``IssueTimeline.comment_reactions``
        being loaded (``lazy="selectin"``), so this costs no extra query per
        event.
        """
        buckets: OrderedDict[str, dict] = OrderedDict(
            (key, {"emoji_key": key, "count": 0, "user_ids": [], "reacted_by_me": False})
            for key in ALLOWED_REACTIONS
        )

        for reaction in event.comment_reactions or []:
            bucket = buckets.get(reaction.emoji_key)
            if bucket is None:
                continue  # key retired from the allowlist — hide it
            bucket["count"] += 1
            bucket["user_ids"].append(reaction.user_id)
            if current_user_id is not None and reaction.user_id == current_user_id:
                bucket["reacted_by_me"] = True

        return [b for b in buckets.values() if b["count"] > 0]


# Module-level singleton
reaction_service = ReactionService()
