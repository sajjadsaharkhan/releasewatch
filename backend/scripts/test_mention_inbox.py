"""Standalone script to test the mention → inbox fan-out end-to-end.

Run inside the api container:
    docker compose exec api python scripts/test_mention_inbox.py

It picks the first two active users, creates a real comment mentioning user B
as user A, then checks the inbox_items table to confirm a row was created.
"""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("test_mention_inbox")


async def main() -> None:
    from sqlalchemy import select, delete
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

    from app.config import settings
    # Import all models so SQLAlchemy can configure mappers before any query
    import app.db.models.user
    import app.db.models.project
    import app.db.models.release
    import app.db.models.issue
    import app.db.models.issue_cycle
    import app.db.models.issue_timeline
    import app.db.models.issue_attachment
    import app.db.models.inbox_item
    import app.db.models.label
    import app.db.models.regression_history
    import app.db.models.system_setting
    from app.db.models.inbox_item import InboxItem, InboxEventType
    from app.db.models.issue import Issue
    from app.db.models.user import User
    from app.services.inbox_service import inbox_service

    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        # ── pick two distinct active users ───────────────────────────────────
        users_result = await db.execute(
            select(User).where(User.is_active.is_(True)).limit(3)
        )
        users = list(users_result.scalars().all())
        if len(users) < 2:
            logger.error("Need at least 2 active users in DB. Found %d.", len(users))
            await engine.dispose()
            sys.exit(1)

        actor = users[0]
        mentioned = users[1]
        logger.info("actor: id=%s username=%s", actor.id, actor.username)
        logger.info("mentioned: id=%s username=%s", mentioned.id, mentioned.username)

        # ── pick any issue ────────────────────────────────────────────────────
        issue_result = await db.execute(select(Issue).limit(1))
        issue = issue_result.scalar_one_or_none()
        if issue is None:
            logger.error("No issues in DB.")
            await engine.dispose()
            sys.exit(1)
        logger.info("issue: id=%s number=%s", issue.id, issue.issue_number)

        # ── wipe any existing mention items for the mentioned user on this issue
        await db.execute(
            delete(InboxItem).where(
                InboxItem.user_id == mentioned.id,
                InboxItem.issue_id == issue.id,
                InboxItem.event_type == InboxEventType.mention,
            )
        )
        await db.commit()
        logger.info("cleaned up pre-existing mention items")

        # ── TEST 1: explicit ID path ──────────────────────────────────────────
        logger.info("=== TEST 1: explicit mentioned_user_ids ===")
        items = await inbox_service.fan_out(
            db=db,
            trigger=InboxEventType.mention,
            issue=issue,
            actor=actor,
            timeline_event=None,
            extra_meta={
                "body": f"hey @{mentioned.username}",
                "mentioned_user_ids": [str(mentioned.id)],
            },
        )
        await db.commit()
        logger.info("TEST 1 items_created=%d (expected 1 if actor != mentioned)", len(items))
        for it in items:
            logger.info("  → InboxItem id=%s user_id=%s type=%s", it.id, it.user_id, it.event_type)

        # ── clean up TEST 1 result ────────────────────────────────────────────
        await db.execute(
            delete(InboxItem).where(InboxItem.id.in_([it.id for it in items]))
        )
        await db.commit()

        # ── TEST 2: regex fallback path (no explicit IDs) ─────────────────────
        logger.info("=== TEST 2: regex fallback — body contains @%s ===", mentioned.username)
        items2 = await inbox_service.fan_out(
            db=db,
            trigger=InboxEventType.mention,
            issue=issue,
            actor=actor,
            timeline_event=None,
            extra_meta={
                "body": f"hey @{mentioned.username} what do you think?",
                "mentioned_user_ids": [],
            },
        )
        await db.commit()
        logger.info("TEST 2 items_created=%d (expected 1 if actor != mentioned)", len(items2))
        for it in items2:
            logger.info("  → InboxItem id=%s user_id=%s type=%s", it.id, it.user_id, it.event_type)

        # ── clean up TEST 2 result ────────────────────────────────────────────
        await db.execute(
            delete(InboxItem).where(InboxItem.id.in_([it.id for it in items2]))
        )
        await db.commit()

        # ── summary ───────────────────────────────────────────────────────────
        logger.info("=== SUMMARY ===")
        logger.info("TEST 1 (explicit ids):  %s", "PASS" if len(items) == 1 else "FAIL (got %d)" % len(items))
        logger.info("TEST 2 (regex fallback): %s", "PASS" if len(items2) == 1 else "FAIL (got %d)" % len(items2))

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
