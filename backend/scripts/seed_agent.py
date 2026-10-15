# ruff: noqa: E501 — seed prose (Markdown bodies) reads better unwrapped.
"""Seed agent content (slice 17) on top of ``scripts/seed.py``'s sample data.

Usage:
    docker compose exec api python -m scripts.seed_agent     # or: make seed-agent

Gives three developers an MCP token each (created revoked, so nobody holds a
usable value and the profile lists stay clean — the rows only anchor the
mark), then, acting through each token the way ``/mcp`` does, files bugs and
technical-debt tasks, adds internal notes, fills empty fields and reports a
recurrence. Everything goes through the same services as the MCP tools, with
the agent context set, so the rows are exactly what an agent would write —
Agent badge, origin filter and all. A person's reply is added too, for
contrast. Telegram sends are suppressed; inbox rows are written as usual.

Additive and safe to re-run: it stops if its first bug already exists.
Attachments are added only when S3 is reachable (the file must exist).
"""

import asyncio
import contextlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent_context import agent_token_id
from app.core.redis_client import close_redis, init_redis
from app.db.models.issue import Issue, IssueType, Priority
from app.db.models.mcp_token import McpToken
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import close_engine, get_engine, init_engine
from app.schemas.issue import IssueCreate, RecurrenceCreate
from app.services.mcp_token_service import hash_value

MARKER_TITLE = "Reactions disappear from group chat messages after a page refresh"

NOW = datetime.now(tz=UTC)

BUG_REACTIONS = """## Summary
Reactions on messages in group chats disappear after the page is refreshed. The reaction is saved for a short time and then lost.

## Observed behavior
1. A user adds a 👍 reaction to a message in a group chat.
2. The reaction shows at once.
3. After a refresh, the reaction is gone. Other members never see it.

## Expected behavior
The reaction stays after a refresh, and every member of the group sees it.

## Evidence
| Source | What it shows |
|---|---|
| `kibana-chat-errors-20261014.log` | 412 `409 Conflict` responses from `POST /v1/chat/react` in 24 hours, all in group chats |
| API logs | Private chats return `200`; only group chats fail |

## Impact
All group chats on web and mobile. About 3% of reactions are lost (412 of 13,900).

## Suspected cause
`ReactionService.add` writes the reaction with the group's cached `version`. When another member posts first, the version is stale, the write returns `409`, and the client does not retry.

## Code references
- `api/chat/reactions.py:88` — the version check
- `web/src/chat/useReactions.ts:41` — the optimistic update that is never rolled back
"""

BUG_WEBHOOK = """## Summary
The webhook retry worker sends the same delivery two or three times when the receiver answers slowly.

## Observed behavior
A receiver that answers after 10 seconds gets the same event again. The first attempt is not cancelled, so both arrive.

## Expected behavior
Each event arrives once. A slow answer is a timeout, and the next attempt waits for the backoff.

## Evidence
| Source | What it shows |
|---|---|
| Worker logs, 2026-10-14 | 1,240 events delivered twice, all with a first attempt longer than 10 s |

## Suspected cause
`deliver()` uses a 10 s client timeout, but the job timeout is 8 s. The job is retried while the first request is still open.

## Code references
- `gateway/webhooks/worker.py:57` — `JOB_TIMEOUT = 8`
- `gateway/webhooks/client.py:22` — `timeout=10`
"""

DEBT_S3_RETRY = """## Summary
The S3 client has its own retry loop. botocore already retries, so a failed upload is tried up to 15 times.

## Current state
`storage/s3.py` wraps every call in a `for attempt in range(5)` loop with a fixed 1 s sleep. botocore's standard mode adds 3 attempts inside each one.

## Risk
A short S3 outage blocks a request worker for up to 75 s. Errors are logged five times, which hides the first cause.

## Suggested approach
Remove the loop. Set `retries={"mode": "standard", "max_attempts": 4}` in the client `Config`, and log once on the final failure.

## Code references
- `gateway/storage/s3.py:31-58`
"""

DEBT_IMAGE_CACHE = """## Summary
The legacy image cache module is not used since the move to the platform image loader, but it is still compiled into the app.

## Current state
`ImageCacheLegacy` (1,900 lines) has no callers. It adds 140 KB to the iOS binary and its tests run on every build.

## Suggested approach
Delete the module and its tests. Remove the `legacyImageCache` feature flag from the remote config.

## Code references
- `ios/Shared/ImageCacheLegacy/` — the whole folder
- `android/app/src/main/java/cache/LegacyImageCache.kt`
"""

NOTE_AUTH = """Root cause found. The refresh request sends the **expired** access token in the `Authorization` header, so the gateway rejects the refresh itself and the client tries again.

Fix: send the refresh token only, without the access token.

- PR: https://git.example.com/mobile/app/pull/1482
- Verified on iOS 17.4 and Android 14 with a token that expires after 30 s."""

NOTE_CHECKOUT = """The crash is a `nil` merchant identifier. It happens when the Apple Pay sheet opens before the payment config request completes.

| Build | Reproduced |
|---|---|
| 2.4.1 (412) | 7 of 10 tries |
| 2.4.1 (413), with the fix | 0 of 20 tries |

PR: https://git.example.com/mobile/app/pull/1479"""

NOTE_WEBHOOK = """Measured the queue during the flood: 38,000 pending jobs, 92% are retries of the same 14 events. The receivers answered in 11–14 s.

This is the same cause as the duplicate deliveries in the new bug I filed. Fixing the timeout mismatch should stop the flood too."""

LOG_BYTES = (
    b"2026-10-14T09:12:03Z ERROR POST /v1/chat/react 409 Conflict chat=group:8812 version=41\n"
    b"2026-10-14T09:12:05Z ERROR POST /v1/chat/react 409 Conflict chat=group:8812 version=41\n"
    b"2026-10-14T09:13:40Z ERROR POST /v1/chat/react 409 Conflict chat=group:1290 version=7\n"
)


@contextlib.contextmanager
def as_agent(token: McpToken):
    """Write as ``token``'s agent — what ``McpEndpoint`` does for one request."""
    reset = agent_token_id.set(token.id)
    try:
        yield
    finally:
        agent_token_id.reset(reset)


def _silence_telegram() -> None:
    """Seed data never sends a real Telegram message."""
    from app.tasks.notifications import send_telegram_notification

    send_telegram_notification.apply_async = lambda *a, **k: None


async def _token(db: AsyncSession, user: User, name: str) -> McpToken:
    value = "rwm_" + secrets.token_urlsafe(32)
    token = McpToken(
        user_id=user.id, name=name, token_hash=hash_value(value), token_prefix=value[:12],
        created_at=NOW - timedelta(days=3), expires_at=NOW + timedelta(days=87),
        revoked_at=NOW, revoked_by_id=user.id,
    )
    db.add(token)
    await db.flush()
    return token


async def _upload_log(file_name: str, data: bytes) -> dict | None:
    """Put a small file in S3 for an attachment; ``None`` when S3 is unreachable."""
    from app.core.s3 import s3_service

    try:
        stored = await asyncio.to_thread(
            s3_service.upload_file, data, "attachment", file_name, "text/plain",
        )
    except Exception as exc:  # noqa: BLE001 — any S3 failure means "no attachments"
        print(f"  S3 unreachable, skipping attachments ({type(exc).__name__})")
        return None
    return stored


async def seed(db: AsyncSession) -> None:
    from app.services.attachment_service import attachment_service
    from app.services.issue_service import issue_service
    from app.services.recurrence_service import recurrence_service
    from app.services.timeline_service import timeline_service

    async def user(username: str) -> User:
        found = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
        if found is None:
            raise SystemExit(f"User {username!r} not found — run `make seed` first.")
        return found

    async def project(slug: str) -> Project:
        found = (await db.execute(select(Project).where(Project.slug == slug))).scalar_one_or_none()
        if found is None:
            raise SystemExit(f"Project {slug!r} not found — run `make seed` first.")
        return found

    async def seeded(title: str) -> Issue | None:
        issue = (await db.execute(
            select(Issue).where(Issue.title == title, Issue.deleted_at.is_(None))
        )).scalars().first()
        if issue is None:
            print(f"  (skipped: no seeded item {title!r})")
        return issue

    if (await db.execute(select(Issue.id).where(Issue.title == MARKER_TITLE))).first():
        print("Agent content is already seeded — nothing to do.")
        return

    sajjad, tom, ana, priya = [await user(u) for u in ("sajjad", "tom", "ana", "priya")]
    mobile, api = await project("mobile-app"), await project("api-gateway")

    print("Seeding MCP tokens (revoked — they only anchor the agent mark)...")
    claude = await _token(db, sajjad, "Claude Code — laptop")
    codex = await _token(db, tom, "Codex — workstation")
    zcode = await _token(db, ana, "ZCode — desktop")

    print("Filing items through agents...")
    with as_agent(claude):
        reactions = await issue_service.create(db, IssueCreate(
            type=IssueType.bug, project_id=mobile.id, title=MARKER_TITLE,
            description=BUG_REACTIONS,
            reproduction_steps=[
                {"step_order": 1, "description": "Open a group chat with two or more members"},
                {"step_order": 2, "description": "Add a 👍 reaction to the last message",
                 "expected_result": "The reaction shows", "actual_result": "The reaction shows"},
                {"step_order": 3, "description": "Refresh the page",
                 "expected_result": "The reaction is still there",
                 "actual_result": "The reaction is gone"},
            ],
            curl_command=(
                "curl -X POST 'https://api.example.com/v1/chat/react' "
                "-H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' "
                "--data '{\"message_id\": 99812, \"emoji\": \"👍\", \"version\": 41}'"
            ),
            environment_name="staging", environment_browser="Chrome 130",
            environment_os="macOS 15.1",
        ), sajjad, into_triage=True)
        stored = await _upload_log("kibana-chat-errors-20261014.log", LOG_BYTES)
        if stored is not None:
            await attachment_service.add(
                db, reactions.id, sajjad.id, file_name="kibana-chat-errors-20261014.log",
                s3_key=stored["s3_key"], mime_type="text/plain",
                file_size_bytes=len(LOG_BYTES), attachment_type="log",
            )
        s3_debt = await issue_service.create(db, IssueCreate(
            type=IssueType.task, project_id=api.id,
            title="Replace the hand-written retry loop in the S3 client with botocore retries",
            description=DEBT_S3_RETRY, priority=Priority.medium, is_tech_debt=True,
        ), sajjad)

    with as_agent(codex):
        webhook = await issue_service.create(db, IssueCreate(
            type=IssueType.bug, project_id=api.id,
            title="Webhook retry worker sends duplicate deliveries after a slow response",
            description=BUG_WEBHOOK,
            environment_name="production",
            assignee_id=tom.id,
        ), tom, into_triage=True)
        cache_debt = await issue_service.create(db, IssueCreate(
            type=IssueType.task, project_id=mobile.id,
            title="Remove the unused legacy image cache module from both apps",
            description=DEBT_IMAGE_CACHE, priority=Priority.low, is_tech_debt=True,
            assignee_id=tom.id,
        ), tom)
    print(f"  Filed {len([reactions, s3_debt, webhook, cache_debt])} items")

    print("Adding agent notes, field fills and a recurrence...")
    with as_agent(claude):
        if (auth := await seeded("Auth token refresh causes 401 loop")) is not None:
            await timeline_service.add_comment(db, auth, sajjad, NOTE_AUTH, is_internal=True)
        if (checkout := await seeded("Crash on checkout with Apple Pay")) is not None:
            await timeline_service.add_comment(db, checkout, sajjad, NOTE_CHECKOUT, is_internal=True)
        if (upload := await seeded("Profile image upload fails >5MB")) is not None:
            await issue_service.update(db, upload.id, {
                "reproduction_steps": [
                    {"step_order": 1, "description": "Open Profile → Edit photo"},
                    {"step_order": 2, "description": "Choose a 6 MB JPEG",
                     "expected_result": "The photo uploads",
                     "actual_result": "\"Upload failed\" after 30 s"},
                ],
                "curl_command": (
                    "curl -X PUT 'https://api.example.com/v1/me/avatar' "
                    "-H 'Authorization: Bearer <token>' --data-binary @photo-6mb.jpg"
                ),
                "environment_os": "iOS 17.4", "environment_build_hash": "a41f9c2",
            }, sajjad)

    with as_agent(zcode):
        if (flood := await seeded("Webhook retries flood the queue")) is not None:
            await timeline_service.add_comment(db, flood, ana, NOTE_WEBHOOK, is_internal=True)
        if (push := await seeded("Push notifications not delivered on iOS 17")) is not None:
            await recurrence_service.report(db, push, RecurrenceCreate(comment=(
                "Happened again on build 2.4.1 (413): 3 of 10 silent pushes were not "
                "delivered to an iPhone 15 on iOS 17.4. Same APNs error: `BadDeviceToken` "
                "after the token refresh."
            )), ana)

    # A person answers the agent's bug — people's content, no badge.
    await timeline_service.add_comment(
        db, reactions, priya,
        "Reproduced on Firefox too. It only happens when someone else posts in the "
        "group between the reaction and the refresh.",
        is_internal=False,
    )
    await db.commit()
    keys = ", ".join(f"{'BUG' if i.type == IssueType.bug else 'TASK'}-{i.issue_number}"
                     for i in (reactions, webhook, s3_debt, cache_debt))
    print(f"  Done — agent items: {keys}")
    print("\nAgent seed complete. Filter by Origin → Agent on Triage, Backlog "
          "(Show technical debt) and Technical debt to find them.")


async def main() -> int:
    _silence_telegram()
    await init_engine()
    await init_redis()
    try:
        from sqlalchemy.ext.asyncio import async_sessionmaker

        async with async_sessionmaker(get_engine(), expire_on_commit=False)() as db:
            await seed(db)
    finally:
        await close_redis()
        await close_engine()
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
