"""The MCP read tools and the ``rw://item/{key}`` resource (slice 16).

docs/phase-2/16-mcp-read-tools.md, prd-mcp.md FR-M02–M09, FR-M21–M23, FR-M36,
A.6–A.8. Each tool acts as the token's owner with exactly their visibility
(BR-M03) and calls the services the web app uses — this module only resolves
display keys, project keys, release versions and usernames to rows, and shapes
the answer. Inputs never carry ids, except ``attachment_id``.

Every answer is structured content plus its Markdown rendering
(``app/mcp_server/markdown.py``), built from the same dict. ``via_agent`` says
whether an item, timeline entry or attachment was written through MCP (slice 17).
"""

import asyncio
import base64
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import HTTPException
from mcp.server.mcpserver.exceptions import ResourceNotFoundError
from mcp.types import CallToolResult, ImageContent
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import DomainError
from app.core.s3 import s3_service
from app.db.models.issue import Issue, IssueStatus, IssueType, issue_key
from app.db.models.issue_attachment import IssueAttachment
from app.db.models.issue_cycle import IssueCycle
from app.db.models.issue_timeline import SIGNIFICANT_TIMELINE_EVENTS, IssueTimeline
from app.db.models.project import Project
from app.db.models.release import Release, ReleaseKind
from app.db.models.user import User
from app.mcp_server import markdown
from app.mcp_server.results import ToolRefusal, error_result, not_found, tool_result
from app.mcp_server.server import db_session, principal_user, request_now, server
from app.search import duplicate_hints, jev_settings, similar
from app.search.retrieval import Filters, search
from app.services import container_service as containers
from app.services.authz import find_visible_issue_by_key, sees_internal
from app.services.backlog_service import tech_debt_page
from app.services.queue_service import queue_service
from app.services.release_service import is_overdue, progress, release_service
from app.services.timeline_service import TimelineService
from app.services.triage_service import TriageService

#: An image at most this big comes back as an image the agent can see (FR-M04).
INLINE_IMAGE_MAX_BYTES = 5 * 1024 * 1024
#: How long a download link from ``rw_get_attachment`` works.
DOWNLOAD_LINK_SECONDS = 15 * 60
#: ``TimelineService.list_timeline`` page size while reading a whole timeline.
_TIMELINE_PAGE = 200
#: The most technical-debt tasks one ``rw_tech_debt`` call returns.
TECH_DEBT_LIMIT = 100


def _value(v):
    return getattr(v, "value", v)


# ── Shared shapes ─────────────────────────────────────────────────────────────


def _person(user: User | None) -> dict | None:
    return {"username": user.username, "name": user.name} if user is not None else None


def _project(project: Project) -> dict:
    return {"key": project.slug, "name": project.name}


def _key(issue: Issue) -> str:
    return issue_key(issue.type, issue.issue_number)


def _row(issue: Issue) -> dict:
    """One item in a list: what an agent needs to pick it, nothing more.
    ``assignee`` must be loaded."""
    return {
        "key": _key(issue),
        "type": _value(issue.type),
        "title": issue.title,
        "status": _value(issue.status),
        "priority": _value(issue.priority),
        "assignee": _person(issue.assignee),
        "is_release_blocker": issue.is_release_blocker,
        "due_date": issue.due_date,
        "via_agent": issue.via_agent,
    }


async def _run(build: Callable[[AsyncSession, User], Awaitable[CallToolResult]]) -> CallToolResult:
    """Run one tool call as the token's owner, in one transaction: committed when
    ``build`` returns, rolled back when it refuses. A refusal — the tool's own,
    a service's ``DomainError``, or a 404 — becomes a tool error (A.8)."""
    try:
        async with db_session() as db:
            return await build(db, await principal_user(db))
    except ToolRefusal as refusal:
        return error_result(refusal)
    except DomainError as err:
        return error_result(ToolRefusal(err.code, err.detail))
    except HTTPException as err:
        if err.status_code == 404:
            return error_result(not_found("It"))
        raise


async def _project_by_key(db: AsyncSession, key: str) -> Project:
    project = (await db.execute(
        select(Project).where(func.lower(Project.slug) == key.strip().lower())
    )).scalar_one_or_none()
    if project is None:
        raise not_found(f"Project {key!r}")
    return project


async def _issue_by_key(db: AsyncSession, key: str, user: User, *options) -> Issue:
    issue = await find_visible_issue_by_key(db, key, user, *options)
    if issue is None:
        raise not_found(f"Item {key!r}")
    return issue


# ── rw_my_queue (FR-M02) ──────────────────────────────────────────────────────


@server.tool(
    name="rw_my_queue",
    description=(
        "Your personal queue in queue order — what to work on next: items In progress "
        "first, then pinned items, then the rest. Each entry has key, type, title, project, "
        "status (Rejected included), priority, pin, cycle number and due date."
    ),
)
async def rw_my_queue() -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        rows = await queue_service.queue(db, user)
        cycle_ids = [i.current_cycle_id for _, i in rows if i.current_cycle_id is not None]
        cycles = {}
        if cycle_ids:
            cycles = {c.id: c.cycle_number for c in (await db.execute(
                select(IssueCycle).where(IssueCycle.id.in_(cycle_ids))
            )).scalars()}

        def entry(group: str, e, issue: Issue) -> dict:
            return {
                "group": group,
                "key": _key(issue),
                "type": _value(issue.type),
                "title": issue.title,
                "project": _project(issue.project),
                "status": _value(issue.status),
                "priority": _value(issue.priority),
                "pinned": e.is_pinned,
                "cycle_number": cycles.get(issue.current_cycle_id),
                "due_date": issue.due_date,
            }

        in_progress = IssueStatus.in_progress.value
        items = [entry("in_progress", e, i) for e, i in rows if _value(i.status) == in_progress]
        items += [
            entry("pinned" if e.is_pinned else "rest", e, i)
            for e, i in rows if _value(i.status) != in_progress
        ]
        data = {"items": items}
        return tool_result(data, markdown.queue(data))

    return await _run(build)


# ── rw_get_item (FR-M03) and rw://item/{key} (FR-M36) ─────────────────────────


async def _whole_timeline(db: AsyncSession, issue_id: int, user: User) -> list[IssueTimeline]:
    """Every event the user may see, oldest first — pagination stays internal."""
    timeline = TimelineService()
    events: list[IssueTimeline] = []
    page = 1
    while True:
        batch, total = await timeline.list_timeline(
            db, issue_id, page=page, size=_TIMELINE_PAGE, include_internal=sees_internal(user),
        )
        events += batch
        if not batch or len(events) >= total:
            return events
        page += 1


def _entry(event: IssueTimeline) -> dict:
    return {
        "id": event.id,
        "type": _value(event.event_type),
        "author": _person(event.actor),
        "at": event.created_at,
        "internal": event.is_internal,
        "body": event.body,
        "meta": event.meta or {},
        "via_agent": event.via_agent,
    }


async def item_context(db: AsyncSession, user: User, key: str, full_timeline: bool) -> dict:
    """Everything ``rw_get_item`` returns for one item."""
    issue = await _issue_by_key(
        db, key, user,
        selectinload(Issue.project), selectinload(Issue.release),
        selectinload(Issue.reporter), selectinload(Issue.assignee),
    )
    events = await _whole_timeline(db, issue.id, user)
    cycles = list((await db.execute(
        select(IssueCycle)
        .where(IssueCycle.issue_id == issue.id)
        .options(selectinload(IssueCycle.release), selectinload(IssueCycle.delivered_by))
        .order_by(IssueCycle.cycle_number)
    )).scalars())
    attachments = (await db.execute(
        select(IssueAttachment)
        .where(IssueAttachment.issue_id == issue.id)
        .options(selectinload(IssueAttachment.uploader))
        .order_by(IssueAttachment.created_at, IssueAttachment.id)
    )).scalars().all()

    reject = None
    current = next((c for c in cycles if c.id == issue.current_cycle_id), None)
    if _value(issue.status) == IssueStatus.rejected.value and current is not None:
        comment = next((e for e in events if e.id == current.start_comment_id), None)
        reject = {
            "reason": _value(current.start_reason),
            "comment": _entry(comment) if comment is not None else None,
        }

    significant = {t.value for t in SIGNIFICANT_TIMELINE_EVENTS}
    shown = events if full_timeline else [
        e for e in events if _value(e.event_type) in significant
    ]
    release = issue.release
    return {
        "key": _key(issue),
        "type": _value(issue.type),
        "title": issue.title,
        "status": _value(issue.status),
        "priority": _value(issue.priority),
        "source": _value(issue.source),
        "project": _project(issue.project),
        "container": (
            {
                "kind": _value(release.kind), "name": release.version,
                "status": _value(release.status),
            }
            if release is not None else None
        ),
        "description": issue.description,
        "reproduction_steps": issue.reproduction_steps or [],
        "curl_command": issue.curl_command,
        "environment": {
            "name": issue.environment_name,
            "browser": issue.environment_browser,
            "os": issue.environment_os,
            "build_hash": issue.environment_build_hash,
            "staging_url": issue.environment_staging_url,
        },
        "labels": issue.labels or [],
        "is_release_blocker": issue.is_release_blocker,
        "is_tech_debt": issue.is_tech_debt,
        "recurrence_count": issue.recurrence_count or 1,
        "due_date": issue.due_date,
        "cancel_reason": _value(issue.cancel_reason),
        "reporter": _person(issue.reporter),
        "assignee": _person(issue.assignee),
        "via_agent": issue.via_agent,
        "created_at": issue.created_at,
        "updated_at": issue.updated_at,
        "completed_at": issue.completed_at,
        "reject": reject,
        "cycles": [
            {
                "number": c.cycle_number,
                "start_reason": _value(c.start_reason),
                "container": c.release.version if c.release is not None else None,
                "started_at": c.started_at,
                "picked_up_at": c.picked_up_at,
                "submitted_at": c.submitted_at,
                "verified_at": c.verified_at,
                "closed_at": c.closed_at,
                "delivered_by": _person(c.delivered_by),
            }
            for c in cycles
        ],
        "attachments": [
            {
                "id": a.id,
                "file_name": a.file_name,
                "mime_type": a.mime_type,
                "size": a.file_size_bytes,
                "kind": _value(a.attachment_type),
                "author": _person(a.uploader),
                "at": a.created_at,
                "via_agent": a.via_agent,
            }
            for a in attachments
        ],
        "full_timeline": full_timeline,
        "timeline": [_entry(e) for e in shown],
    }


@server.tool(
    name="rw_get_item",
    description=(
        "One item by its key (BUG-42, TASK-118; any case): every field you can see — "
        "description, reproduction steps, the full cURL command, environment — its container, "
        "cycles, the reject comment of a Rejected item, attachments, and the timeline. By "
        "default the timeline has comments, internal notes and significant events (filed, "
        "triaged, status changes, recurrences, duplicates); full_timeline=true returns every event."
    ),
)
async def rw_get_item(
    key: Annotated[str, Field(description="The item's key, e.g. BUG-42 or TASK-118.")],
    full_timeline: Annotated[bool, Field(description="Return every timeline event.")] = False,
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        data = await item_context(db, user, key, full_timeline)
        return tool_result(data, markdown.item(data))

    return await _run(build)


@server.resource(
    "rw://item/{key}",
    name="item",
    title="Releasewatch item",
    description="One item's default rw_get_item context as Markdown, e.g. rw://item/BUG-42.",
    mime_type="text/markdown",
)
async def item_resource(key: str) -> str:
    try:
        async with db_session() as db:
            return markdown.item(await item_context(db, await principal_user(db), key, False))
    except ToolRefusal as refusal:
        raise ResourceNotFoundError(refusal.message) from None


# ── rw_get_attachment (FR-M04) ────────────────────────────────────────────────


@server.tool(
    name="rw_get_attachment",
    description=(
        "One attachment of an item. An image of 5 MB or less comes back as an image you can "
        "see; any other file as a short-lived download link you can fetch with your shell."
    ),
)
async def rw_get_attachment(
    key: Annotated[str, Field(description="The item's key, e.g. BUG-42.")],
    attachment_id: Annotated[int, Field(description="The attachment's id, from rw_get_item.")],
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        issue = await _issue_by_key(db, key, user)
        att = (await db.execute(
            select(IssueAttachment).where(
                IssueAttachment.id == attachment_id, IssueAttachment.issue_id == issue.id,
            )
        )).scalar_one_or_none()
        if att is None:
            raise ToolRefusal(
                "attachment_not_found",
                f"{_key(issue)} has no attachment {attachment_id}. "
                "Read its attachments with rw_get_item.",
            )
        data = {
            "id": att.id, "file_name": att.file_name, "mime_type": att.mime_type,
            "size": att.file_size_bytes,
        }
        small = att.file_size_bytes is None or att.file_size_bytes <= INLINE_IMAGE_MAX_BYTES
        if att.mime_type.startswith("image/") and small:
            # The one deliberate exception to "the API never handles file bytes" (A.6).
            raw = await asyncio.to_thread(
                s3_service.get_object_bytes, att.s3_key, INLINE_IMAGE_MAX_BYTES,
            )
            if raw is not None:
                image = ImageContent(
                    type="image", data=base64.b64encode(raw).decode(), mime_type=att.mime_type,
                )
                return tool_result(data, markdown.attachment(data), image)
        expires_at = request_now() + timedelta(seconds=DOWNLOAD_LINK_SECONDS)
        data |= {
            "download_url": s3_service.generate_presigned_download(
                att.s3_key, expiry_seconds=DOWNLOAD_LINK_SECONDS,
            ),
            "expires_at": expires_at,
        }
        return tool_result(data, markdown.attachment(data))

    return await _run(build)


# ── rw_search (FR-M05) ────────────────────────────────────────────────────────


def _hit(row: dict) -> dict:
    return {
        "key": row["key"],
        "type": row["type"],
        "title": row["title"],
        "status": row["status"],
        "priority": row["priority"],
        "is_cancelled": row["is_cancelled"],
        "project": {"key": row["project"]["slug"], "name": row["project"]["name"]},
        "snippet": row["snippet"],
        "snippet_source": row["snippet_source"],
    }


@server.tool(
    name="rw_search",
    description=(
        "Search items the way the search page does — Persian, English and mixed text. With "
        "a project key it searches that project; without one, every project you can see. "
        "Less relevant results come back separately; cancelled items are found and marked."
    ),
)
async def rw_search(
    query: Annotated[str, Field(min_length=1, max_length=500, description="What to look for.")],
    project: Annotated[
        str | None, Field(description="A project key; omit to search every project."),
    ] = None,
    type: Annotated[list[IssueType] | None, Field(description="Only these types.")] = None,  # noqa: A002
    status: Annotated[list[IssueStatus] | None, Field(description="Only these statuses.")] = None,
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        project_id = (await _project_by_key(db, project)).id if project else None
        ranked = await search(db, user, query, filters=Filters(
            project_id=project_id,
            types=[t.value for t in type or []],
            statuses=[s.value for s in status or []],
        ), mode="page")
        # Queries are never logged (BR-S20).
        data = {
            "jev_used": ranked.jev_used,
            "results": [_hit(r) for r in ranked.results],
            "less_relevant": [_hit(r) for r in ranked.less_relevant],
        }
        return tool_result(data, markdown.search(data))

    return await _run(build)


# ── rw_find_similar (FR-M06, FR-M21–M23) ──────────────────────────────────────


def _candidate(row: dict) -> dict:
    issue = row["issue"]
    return {
        "issue": {
            "key": issue["key"],
            "type": issue["type"],
            "title": issue["title"],
            "status": issue["status"],
            "project": {"key": issue["project"]["slug"], "name": issue["project"]["name"]},
        },
        "verdict": row.get("verdict"),
        "confidence": row.get("confidence"),
    }


async def duplicate_check(
    db: AsyncSession, user: User, title: str, description: str | None,
) -> dict:
    """The duplicate check (FR-M21–M23): Jev's verdicts when it is on, else the
    closest local matches with no verdict. ``rw_find_similar`` and every filing
    (``rw_file_bug``, ``rw_file_tech_debt``) run exactly this."""
    judged = await similar.tech_suggestions(db, user, title, description)
    jev_used = judged is not None
    rows = judged if jev_used else await similar.local_candidates(db, user, title, description)
    return {"jev_used": jev_used, "items": [_candidate(r) for r in rows]}


@server.tool(
    name="rw_find_similar",
    description=(
        "Duplicate check for a draft, across every project you can see; cancelled items are "
        "never candidates. With Jev on, candidates carry a verdict (same or related). With "
        "Jev off, they are the closest local matches with no verdict — judge them yourself "
        "with rw_get_item, and let the developer decide."
    ),
)
async def rw_find_similar(
    type: Annotated[Literal["bug", "task"], Field(description="The draft's type.")],  # noqa: A002
    title: Annotated[str, Field(min_length=1, max_length=500, description="The draft's title.")],
    description: Annotated[str | None, Field(description="The draft's description.")] = None,
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        data = await duplicate_check(db, user, title, description)
        return tool_result(data, markdown.similar(data))

    return await _run(build)


# ── rw_triage_queue (FR-M07) ──────────────────────────────────────────────────


@server.tool(
    name="rw_triage_queue",
    description=(
        "A project's triage queue: its New and Needs info bugs, oldest first, with source, "
        "reporter and recurrence count — and, while Jev is on, each New bug's possible "
        "duplicates with what merging into them would do."
    ),
)
async def rw_triage_queue(
    project: Annotated[str, Field(description="The project key.")],
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        proj = await _project_by_key(db, project)
        hints_on = await jev_settings.is_enabled(db)
        items = []
        for issue in await TriageService.queue(db, user, proj.id):
            hints = (
                await duplicate_hints.hydrate(db, issue.id)
                if hints_on and duplicate_hints.is_hintable(issue) else []
            )
            items.append({
                "key": _key(issue),
                "title": issue.title,
                "status": _value(issue.status),
                "source": _value(issue.source),
                "priority": _value(issue.priority),
                "reporter": _person(issue.reporter),
                "assignee": _person(issue.assignee),
                "recurrence_count": issue.recurrence_count or 1,
                "via_agent": issue.via_agent,
                "created_at": issue.created_at,
                "possible_duplicates": [
                    {
                        "key": h["candidate"]["key"],
                        "type": h["candidate"]["type"],
                        "title": h["candidate"]["title"],
                        "status": h["candidate"]["status"],
                        "confidence": h["confidence"],
                        "merge_effect": h["merge_effect"],
                    }
                    for h in hints
                ],
            })
        data = {"project": _project(proj), "items": items}
        return tool_result(data, markdown.triage_queue(data))

    return await _run(build)


# ── rw_board (FR-M08) ─────────────────────────────────────────────────────────


async def _release_header(
    db: AsyncSession, release: Release, items: list[Issue], now: datetime,
) -> dict:
    counts = await release_service.counts(db, release.id)
    go_nogo_by = await db.get(User, release.go_nogo_by_id) if release.go_nogo_by_id else None
    closed = {IssueStatus.done.value, IssueStatus.cancelled.value}
    return {
        "kind": ReleaseKind.release.value,
        "name": release.version,
        "status": _value(release.status),
        "code_freeze_date": release.code_freeze_date,
        "target_date": release.target_date,
        "released_at": release.released_at,
        "is_overdue": is_overdue(release, now),
        "progress": progress(counts),
        "counts": counts,
        "go_nogo": {
            "status": _value(release.go_nogo_status),
            "note": release.go_nogo_note,
            "by": _person(go_nogo_by),
            "at": release.go_nogo_at,
        },
        "open_blockers": [
            _row(i) for i in items if i.is_release_blocker and _value(i.status) not in closed
        ],
    }


@server.tool(
    name="rw_board",
    description=(
        "A project's work by status. Without a release: the project's Stream, with Done "
        "limited to the last 7 days. With a release version: that release's header — "
        "lifecycle status, dates, progress, Overdue, go/no-go, open release blockers — and "
        "its items by status."
    ),
)
async def rw_board(
    project: Annotated[str, Field(description="The project key.")],
    release: Annotated[
        str | None, Field(description="A release version, e.g. 2.4.0; omit for the Stream."),
    ] = None,
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        proj = await _project_by_key(db, project)
        now = request_now()
        if release is None:
            container = await containers.stream_of(db, proj.id)
        else:
            container = (await db.execute(
                select(Release).where(
                    Release.project_id == proj.id,
                    Release.kind == ReleaseKind.release.value,
                    Release.version == release.strip(),
                    Release.deleted_at.is_(None),
                )
            )).scalar_one_or_none()
            if container is None:
                raise not_found(f"Release {release!r} of {proj.slug}")
        items, done_from, done_to = await release_service.items(db, container, user, now=now)
        header = (
            {"kind": ReleaseKind.stream.value, "name": container.version}
            if container.is_stream else await _release_header(db, container, items, now)
        )
        data = {
            "project": _project(proj),
            "container": header,
            "done_from": done_from,
            "done_to": done_to,
            "columns": [
                {"status": s.value, "items": [_row(i) for i in group]}
                for s in IssueStatus
                if (group := [i for i in items if _value(i.status) == s.value])
            ],
        }
        return tool_result(data, markdown.board(data))

    return await _run(build)


# ── rw_tech_debt (FR-M09) ─────────────────────────────────────────────────────


@server.tool(
    name="rw_tech_debt",
    description=(
        "Technical-debt tasks, highest priority first, then oldest — check what is already "
        "recorded before filing. Filter by project key, statuses and assignee username."
    ),
)
async def rw_tech_debt(
    project: Annotated[
        str | None, Field(description="A project key; omit for every project."),
    ] = None,
    status: Annotated[list[IssueStatus] | None, Field(description="Only these statuses.")] = None,
    assignee: Annotated[str | None, Field(description="An assignee's username.")] = None,
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        proj = await _project_by_key(db, project) if project else None
        assignee_id = None
        if assignee:
            username = assignee.strip().lstrip("@").lower()
            person = (await db.execute(
                select(User).where(func.lower(User.username) == username)
            )).scalar_one_or_none()
            if person is None:
                raise not_found(f"User {assignee!r}")
            assignee_id = person.id
        rows, total = await tech_debt_page(
            db, user,
            project_ids=[proj.id] if proj else None,
            statuses=[s.value for s in status or []],
            assignee_id=assignee_id,
            size=TECH_DEBT_LIMIT,
        )
        data = {
            "total": total,
            "items": [_row(i) | {"project": _project(i.project)} for i in rows],
        }
        return tool_result(data, markdown.tech_debt(data))

    return await _run(build)
