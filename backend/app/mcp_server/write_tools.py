"""The MCP write tools (slice 17).

docs/phase-2/17-mcp-agent-origin-and-write-tools.md, prd-mcp.md FR-M10–FR-M20,
FR-M32, BR-M01, BR-M06, BR-M08–M13, BR-M15, BR-M16, BR-M19, A.6–A.8.

Seven tools: ``rw_upload_prepare``, ``rw_file_bug``, ``rw_file_tech_debt``,
``rw_add_note``, ``rw_attach``, ``rw_fill_field``, ``rw_report_recurrence`` — and
from slice 18 two more for content the agent owns, ``rw_update_own`` and
``rw_delete_own`` (Agent ownership, ``app/agent_ownership.py``).
Each acts as the token's owner (BR-M03) through the services the web app uses;
this module only checks the agent-specific rules (writing checks, fixed
placement, empty fields), resolves keys and usernames, and shapes the answer.
``McpEndpoint`` sets the agent context, so every row a tool writes — side
effects included — is stamped as agent content by the three writers
(``app/core/agent_context.py``). No tool changes status, container, triage
outcome, release state, labels, flags, or a queue (BR-M01).

Uploads: ``rw_upload_prepare`` presigns an S3 upload with the existing logic
and keeps a **pending upload** in Redis for an hour; a filing or ``rw_attach``
consumes it — owner only, once — through ``AttachmentService.add``. The API
never receives the bytes (A.6).
"""

import asyncio
import json
import math
import secrets
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Annotated, Literal

from mcp.types import CallToolResult
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent_ownership import FIELDS
from app.config import settings
from app.core.redis_client import get_redis_raw
from app.core.s3 import s3_service
from app.db.models.inbox_item import InboxEventType
from app.db.models.issue import Issue, IssueStatus, IssueType, Priority
from app.db.models.issue_attachment import AttachmentType, IssueAttachment
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.project import Project
from app.db.models.user import User
from app.mcp_server import markdown
from app.mcp_server.read_tools import _key, _person, _project, _run, duplicate_check
from app.mcp_server.results import ToolRefusal, not_found, tool_result
from app.mcp_server.server import request_now, server
from app.policy import Action, Target
from app.schemas.issue import IssueCreate, RecurrenceCreate
from app.services import agent_ownership_loader
from app.services.attachment_service import attachment_service
from app.services.authz import authorize, find_visible_issue_by_key, issue_target
from app.services.inbox_service import inbox_service
from app.services.issue_service import issue_service
from app.services.recurrence_service import recurrence_service
from app.services.timeline_service import timeline_service

# ── The writing checks (agent-writing-standard.md §9, BR-M19) ────────────────

TITLE_MIN, TITLE_MAX = 15, 90
DESCRIPTION_MAX = 12_000
NOTE_MAX = 3_000

#: An unused upload is forgotten after this long (FR-M10).
UPLOAD_TTL_SECONDS = 60 * 60
_UPLOAD_KEY = "rw:mcp:upload:{}"
#: Above the existing large-file threshold an upload is multipart, in parts this big.
MULTIPART_PART_BYTES = 64 * 1024 * 1024

_CLOSED = {IssueStatus.done.value, IssueStatus.cancelled.value}
EnvironmentName = Literal["production", "staging", "development", "local", "qa"]


def _value(v):
    return getattr(v, "value", v)


# ── The standard in the tool descriptions (slice 18, FR-M31, M5) ─────────────
# The relevant lines of agent-writing-standard.md; the whole standard is the
# resource rw://standards/writing. Each description stays under ~1,500 characters.

_LANGUAGE = (
    " Write English in ASD-STE100 — one idea per sentence, active voice, no "
    "'should' or 'may' — unless the developer explicitly asked for another language. "
    "Full standard: rw://standards/writing."
)
_EVIDENCE = (
    " Evidence is a table: Source | Locator | Time range | What it shows. Every claim "
    "has a row, or starts with **Hypothesis:**, or says Unknown. Never guess a link."
)
_ASK_FIRST = (
    " Show the developer the draft first. Set an assignee or a priority only when the "
    "developer asked or confirmed. If the duplicate check finds candidates, nothing is "
    "filed: read them with rw_get_item and ask the developer; pass file_anyway=true only "
    "if they decide to file."
)


def _check_title(title: str) -> str:
    title = title.strip()
    if not TITLE_MIN <= len(title) <= TITLE_MAX:
        raise ToolRefusal(
            "title_length",
            f"The title has {len(title)} characters; it must have {TITLE_MIN} to {TITLE_MAX}.",
        )
    return title


def _check_description(description: str | None) -> str | None:
    description = (description or "").strip() or None
    if description is not None and len(description) > DESCRIPTION_MAX:
        raise ToolRefusal(
            "description_too_long",
            f"The description has {len(description)} characters; the limit is "
            f"{DESCRIPTION_MAX:,}. Move logs, scripts, and long results to attachments.",
        )
    return description


def _item_url(issue: Issue) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/issue/{_key(issue).lower()}"


# ── Inputs ────────────────────────────────────────────────────────────────────


class StepInput(BaseModel):
    """One reproduction step — one action; steps are numbered in the order given."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(min_length=1, description=(
        "One action, as one imperative sentence, e.g. 'Sign in as a user of customer 1327.' "
        "A precondition is its own step. The environment is not a step."
    ))
    expected_result: str | None = Field(
        None, description="What must happen — only on the step where the problem shows.",
    )
    actual_result: str | None = Field(
        None, description="What happens instead — only on the step where the problem shows.",
    )


class EnvironmentInput(BaseModel):
    """Where the problem happens. Give only what you know."""

    model_config = ConfigDict(extra="forbid")

    name: EnvironmentName | None = Field(None, description="The named environment.")
    browser: str | None = Field(None, max_length=128)
    os: str | None = Field(None, max_length=128)
    build_hash: str | None = Field(None, max_length=64)
    staging_url: str | None = Field(None, max_length=512)

    def fields(self) -> dict[str, str]:
        """The given sub-fields as item columns (``environment_*``)."""
        return {
            f"environment_{name}": value
            for name, value in self.model_dump().items()
            if value not in (None, "")
        }


def _steps(steps: list[StepInput]) -> list[dict]:
    return [
        {"step_order": n, **step.model_dump()} for n, step in enumerate(steps, start=1)
    ]


# ── Pending uploads (A.6) ─────────────────────────────────────────────────────


@dataclass
class PendingUpload:
    upload_id: str
    owner_id: int
    s3_key: str
    file_name: str
    mime_type: str
    size: int
    attachment_type: str
    #: The S3 multipart upload, for a file above the large-file threshold.
    multipart_id: str | None = None


def attachment_type_for(mime_type: str, file_name: str) -> AttachmentType:
    """The attachment type a MIME type implies — what the upload dialog picks."""
    mime = mime_type.lower()
    if mime.startswith("image/"):
        return AttachmentType.screenshot
    if mime.startswith("video/"):
        return AttachmentType.recording
    if file_name.lower().endswith(".log") or mime in ("text/x-log", "text/plain"):
        return AttachmentType.log
    return AttachmentType.other


def _unknown_upload(upload_id: str) -> ToolRefusal:
    return ToolRefusal(
        "unknown_upload",
        f"Upload {upload_id!r} is unknown, already used, expired, or not yours. "
        "Start a new one with rw_upload_prepare.",
    )


async def _uploads_ready(user: User, upload_ids: list[str]) -> list[PendingUpload]:
    """Check every upload before anything is written: it exists, it is the
    user's, it is named once, and its file is in S3 (``unknown_upload``)."""
    redis = await get_redis_raw()
    uploads: list[PendingUpload] = []
    for upload_id in upload_ids:
        raw = await redis.get(_UPLOAD_KEY.format(upload_id))
        if raw is None or any(u.upload_id == upload_id for u in uploads):
            raise _unknown_upload(upload_id)
        upload = PendingUpload(**json.loads(raw))
        if upload.owner_id != user.id:
            raise _unknown_upload(upload_id)
        if upload.multipart_id:
            # Idempotent: a second check finds the upload gone and the object there.
            await asyncio.to_thread(
                s3_service.complete_uploaded_parts, upload.s3_key, upload.multipart_id,
            )
        info = await asyncio.to_thread(s3_service.get_file_info, upload.s3_key)
        if info is None:
            raise ToolRefusal(
                "unknown_upload",
                f"Upload {upload_id!r} has no file yet. Upload the file to the URL from "
                "rw_upload_prepare first.",
            )
        upload.size = info.get("size_bytes") or upload.size
        uploads.append(upload)
    return uploads


async def _attach_uploads(
    db: AsyncSession, issue: Issue, user: User, uploads: list[PendingUpload],
) -> list[IssueAttachment]:
    """Consume the uploads — each once — and attach them to ``issue``. If another
    call consumed one meanwhile, the rest are put back and nothing is attached."""
    redis = await get_redis_raw()
    taken: list[PendingUpload] = []
    for upload in uploads:
        if not await redis.delete(_UPLOAD_KEY.format(upload.upload_id)):
            for back in taken:
                await redis.set(
                    _UPLOAD_KEY.format(back.upload_id), json.dumps(asdict(back)),
                    ex=UPLOAD_TTL_SECONDS,
                )
            raise _unknown_upload(upload.upload_id)
        taken.append(upload)
    return [
        await attachment_service.add(
            db, issue.id, user.id,
            file_name=u.file_name, s3_key=u.s3_key, mime_type=u.mime_type,
            file_size_bytes=u.size, attachment_type=u.attachment_type,
        )
        for u in uploads
    ]


def _attachment(a: IssueAttachment) -> dict:
    return {
        "id": a.id, "file_name": a.file_name, "mime_type": a.mime_type,
        "size": a.file_size_bytes, "kind": _value(a.attachment_type), "via_agent": a.via_agent,
    }


# ── Lookups ───────────────────────────────────────────────────────────────────


async def _open_project(db: AsyncSession, key: str) -> Project:
    project = (await db.execute(
        select(Project).where(
            func.lower(Project.slug) == key.strip().lower(), Project.archived_at.is_(None),
        )
    )).scalar_one_or_none()
    if project is None:
        raise not_found(f"Project {key!r}")
    return project


async def _assignee(db: AsyncSession, user: User, username: str | None) -> int | None:
    """An assignee the developer asked for (FR-M14): ``assign`` and BR-32 apply."""
    if not username:
        return None
    name = username.strip().lstrip("@").lower()
    person = (await db.execute(
        select(User).where(func.lower(User.username) == name)
    )).scalar_one_or_none()
    if person is None:
        raise not_found(f"User {username!r}")
    authorize(user, Action.assign)
    return person.id


async def _item(db: AsyncSession, user: User, key: str) -> Issue:
    issue = await find_visible_issue_by_key(db, key, user, selectinload(Issue.project))
    if issue is None:
        raise not_found(f"Item {key!r}")
    return issue


# ── rw_upload_prepare (FR-M10) ────────────────────────────────────────────────


@server.tool(
    name="rw_upload_prepare",
    description=(
        "Start a file upload — a log, screenshot, script, or export. Returns an upload_id "
        "and where to upload the file with your shell; then pass the upload_id to "
        "rw_file_bug, rw_file_tech_debt, or rw_attach. An unused upload expires after one "
        "hour. Attach a file for a screenshot or recording, a log, script, query or result "
        "set over 20 lines, or a trace, HAR or dump. Cut a log to the relevant time range "
        "and lines. Name files <source>-<content>-<yyyymmdd>.<ext>, e.g. "
        "kibana-chat-errors-20261014.log. Upload only a file the description or a note "
        "refers to by name."
    ),
)
async def rw_upload_prepare(
    file_name: Annotated[str, Field(min_length=1, max_length=255, description="The file's name.")],
    mime_type: Annotated[
        str, Field(min_length=1, max_length=128, description="e.g. text/plain, image/png."),
    ],
    size: Annotated[int, Field(gt=0, description="The file's size in bytes.")],
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        upload_id = f"up_{secrets.token_urlsafe(16)}"
        kind = attachment_type_for(mime_type, file_name)
        now = request_now()
        presign_expires = now + timedelta(seconds=settings.S3_PRESIGN_EXPIRY)
        data: dict = {
            "upload_id": upload_id,
            "expires_at": now + timedelta(seconds=UPLOAD_TTL_SECONDS),
            "upload_url_expires_at": presign_expires,
        }
        multipart_id = None
        if size > settings.S3_LARGE_FILE_THRESHOLD_MB * 1024 * 1024:
            started = await asyncio.to_thread(
                s3_service.create_multipart_upload, "attachment", file_name, mime_type,
            )
            s3_key, multipart_id = started["s3_key"], started["upload_id"]
            parts = math.ceil(size / MULTIPART_PART_BYTES)
            data["multipart"] = {
                "part_size": MULTIPART_PART_BYTES,
                "parts": [
                    {
                        "part_number": n,
                        "url": s3_service.presign_upload_part(s3_key, multipart_id, n),
                    }
                    for n in range(1, parts + 1)
                ],
            }
        else:
            presigned = await asyncio.to_thread(
                s3_service.generate_presigned_upload,
                "attachment", file_name, mime_type, max(1, math.ceil(size / (1024 * 1024))),
            )
            s3_key = presigned["s3_key"]
            data["post"] = {"url": presigned["upload_url"], "fields": presigned["fields"]}

        upload = PendingUpload(
            upload_id=upload_id, owner_id=user.id, s3_key=s3_key, file_name=file_name,
            mime_type=mime_type, size=size, attachment_type=kind.value,
            multipart_id=multipart_id,
        )
        await (await get_redis_raw()).set(
            _UPLOAD_KEY.format(upload_id), json.dumps(asdict(upload)), ex=UPLOAD_TTL_SECONDS,
        )
        return tool_result(data, markdown.upload(data, file_name))

    return await _run(build)


# ── Filing (FR-M11–M15) ───────────────────────────────────────────────────────


async def _file(
    db: AsyncSession,
    user: User,
    data: IssueCreate,
    *,
    upload_ids: list[str] | None,
    file_anyway: bool,
) -> CallToolResult:
    """Check, look for duplicates, create, attach — in that order (slice 17)."""
    authorize(user, Action.create_item)
    if data.is_tech_debt:
        authorize(user, Action.flag_tech_debt, Target(item_type=IssueType.task.value))
    uploads = await _uploads_ready(user, list(upload_ids or []))

    check = await duplicate_check(db, user, data.title, data.description)
    if check["items"] and not file_anyway:
        raise ToolRefusal(
            "duplicates_found",
            "Similar items exist, so nothing was filed. Read them with rw_get_item and ask "
            "the developer: document the existing item, or file anyway with file_anyway=true.",
            data={"jev_used": check["jev_used"], "candidates": check["items"]},
            markdown=markdown.similar(check),
        )

    issue = await issue_service.create(
        db, data, user, into_triage=data.type == IssueType.bug,
    )
    attachments = await _attach_uploads(db, issue, user, uploads)
    issue = (await db.execute(
        select(Issue).where(Issue.id == issue.id).options(
            selectinload(Issue.project), selectinload(Issue.assignee),
        ).execution_options(populate_existing=True)
    )).scalar_one()
    result = {
        "key": _key(issue),
        "type": _value(issue.type),
        "title": issue.title,
        "status": _value(issue.status),
        "priority": _value(issue.priority),
        "project": _project(issue.project),
        "assignee": _person(issue.assignee),
        "is_tech_debt": issue.is_tech_debt,
        "attachments": [_attachment(a) for a in attachments],
        "via_agent": issue.via_agent,
        "url": _item_url(issue),
    }
    return tool_result(result, markdown.filed(result))


@server.tool(
    name="rw_file_bug",
    description=(
        "File a bug into the project's triage queue: New, no container, source Internal, no "
        "priority. Title '<Area>: <observed problem>', 15–90 characters, no period. "
        "Description sections (## headings only): Summary, Observed behavior, Expected "
        "behavior, Evidence (required); Impact, Suspected cause, Code references, Related "
        "items. 150–400 words, 12,000 characters at most. Reproduction steps, cURL and "
        "environment go in their fields, not the description: one action per step, each "
        "precondition (the user, the data) its own step, the environment never a step. Logs and scripts over 20 "
        "lines, screenshots and dumps go in attachments (upload_ids from rw_upload_prepare), "
        "each named in the description." + _EVIDENCE + _ASK_FIRST + " The duplicate check "
        "runs across every project. For a problem in a Done item, file a new bug and name "
        "the Done item under Related items." + _LANGUAGE
    ),
)
async def rw_file_bug(
    project: Annotated[str, Field(description="The project key, from rw_context.")],
    title: Annotated[str, Field(description="15–90 characters.")],
    description: Annotated[
        str | None, Field(description="Markdown, at most 12,000 characters."),
    ] = None,
    reproduction_steps: Annotated[
        list[StepInput] | None,
        Field(description="The steps, in order — one action per step."),
    ] = None,
    curl: Annotated[str | None, Field(description="A cURL command that shows the problem.")] = None,
    environment: Annotated[
        EnvironmentInput | None, Field(description="Where the problem happens."),
    ] = None,
    upload_ids: Annotated[
        list[str] | None, Field(description="Uploads from rw_upload_prepare to attach."),
    ] = None,
    assignee: Annotated[
        str | None, Field(description="A username — only when the developer asked for one."),
    ] = None,
    file_anyway: Annotated[
        bool, Field(description="File even though the duplicate check found candidates."),
    ] = False,
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        clean_title = _check_title(title)
        clean_description = _check_description(description)
        proj = await _open_project(db, project)
        data = IssueCreate(
            type=IssueType.bug,
            project_id=proj.id,
            title=clean_title,
            description=clean_description,
            reproduction_steps=_steps(reproduction_steps or []),
            curl_command=(curl or "").strip() or None,
            assignee_id=await _assignee(db, user, assignee),
            **(environment.fields() if environment else {}),
        )
        return await _file(db, user, data, upload_ids=upload_ids, file_anyway=file_anyway)

    return await _run(build)


@server.tool(
    name="rw_file_tech_debt",
    description=(
        "File a technical-debt task into the project's backlog: To do, category Default, "
        "technical-debt flag set, no container. Check rw_tech_debt first. Title "
        "'<Area>: <what is wrong>', 15–90 characters. Description sections (## headings "
        "only): Summary, Current state, Evidence, Risk, Suggested approach (required); Code "
        "references, Related items. 200–500 words, 12,000 characters at most; long logs and "
        "scripts go in attachments (upload_ids from rw_upload_prepare)." + _EVIDENCE
        + " Priority is Medium: propose one and pass it only if the developer confirmed it."
        + _ASK_FIRST + _LANGUAGE
    ),
)
async def rw_file_tech_debt(
    project: Annotated[str, Field(description="The project key, from rw_context.")],
    title: Annotated[str, Field(description="15–90 characters.")],
    description: Annotated[
        str | None, Field(description="Markdown, at most 12,000 characters."),
    ] = None,
    priority: Annotated[
        Priority | None, Field(description="Only a priority the developer confirmed."),
    ] = None,
    upload_ids: Annotated[
        list[str] | None, Field(description="Uploads from rw_upload_prepare to attach."),
    ] = None,
    assignee: Annotated[
        str | None, Field(description="A username — only when the developer asked for one."),
    ] = None,
    file_anyway: Annotated[
        bool, Field(description="File even though the duplicate check found candidates."),
    ] = False,
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        clean_title = _check_title(title)
        clean_description = _check_description(description)
        proj = await _open_project(db, project)
        data = IssueCreate(
            type=IssueType.task,
            project_id=proj.id,
            title=clean_title,
            description=clean_description,
            priority=priority or Priority.medium,
            is_tech_debt=True,
            assignee_id=await _assignee(db, user, assignee),
        )
        return await _file(db, user, data, upload_ids=upload_ids, file_anyway=file_anyway)

    return await _run(build)


# ── rw_add_note (FR-M16) ──────────────────────────────────────────────────────


@server.tool(
    name="rw_add_note",
    description=(
        "Add an internal note to an item. Always internal: Support never sees it. Markdown; "
        "30–150 words, 3,000 characters at most. New information about an item you did not "
        "file goes here, never into its description. Shapes: a PR link is "
        "'PR: [<PR title>](<url>)' and one sentence on what the PR changes; new evidence is "
        "one sentence with the finding, then an Evidence table; a correction is one sentence "
        "on what was wrong in earlier agent content and what is correct now."
        + _EVIDENCE + _LANGUAGE
    ),
)
async def rw_add_note(
    key: Annotated[str, Field(description="The item's key, e.g. BUG-42.")],
    body: Annotated[str, Field(min_length=1, description="The note, at most 3,000 characters.")],
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        text = body.strip()
        if not text:
            raise ToolRefusal("note_empty", "The note is empty.")
        if len(text) > NOTE_MAX:
            raise ToolRefusal(
                "note_too_long",
                f"The note has {len(text)} characters; the limit is {NOTE_MAX:,}. "
                "Move long output to an attachment.",
            )
        issue = await _item(db, user, key)
        authorize(user, Action.comment_internal, issue_target(issue, issue.project))
        event = await timeline_service.add_comment(db, issue, user, text, is_internal=True)
        data = {
            "key": _key(issue), "note_id": event.id, "internal": True,
            "via_agent": event.via_agent,
        }
        return tool_result(data, f"Added an internal note to {data['key']}.")

    return await _run(build)


# ── rw_attach (FR-M17) ────────────────────────────────────────────────────────


@server.tool(
    name="rw_attach",
    description=(
        "Attach an uploaded file (upload_id from rw_upload_prepare) to an existing item. "
        "On a bug reported by Support, Support sees it. Refer to the file by its name in a "
        "note (rw_add_note) that says what it shows."
    ),
)
async def rw_attach(
    key: Annotated[str, Field(description="The item's key, e.g. BUG-42.")],
    upload_id: Annotated[str, Field(description="The upload, from rw_upload_prepare.")],
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        issue = await _item(db, user, key)
        authorize(user, Action.edit_item, issue_target(issue, issue.project))
        uploads = await _uploads_ready(user, [upload_id])
        [attachment] = await _attach_uploads(db, issue, user, uploads)
        # The notice the upload dialog's confirm sends.
        await inbox_service.fan_out(
            db=db, trigger=InboxEventType.attachment_added, issue=issue, actor=user,
        )
        data = {"key": _key(issue), "attachment": _attachment(attachment)}
        return tool_result(data, f"Attached {attachment.file_name} to {data['key']}.")

    return await _run(build)


# ── rw_fill_field (FR-M18) ────────────────────────────────────────────────────

FillField = Literal["reproduction_steps", "curl", "environment"]


@server.tool(
    name="rw_fill_field",
    description=(
        "Fill an empty field of a bug that is not Done or Cancelled: reproduction_steps (a "
        "list of steps), curl (a cURL command), or environment (an object; every sub-field "
        "you give must be empty). A field that has a value is never changed — add a note "
        "instead. One action per step, as an imperative sentence of 20 words at most; each "
        "precondition (the user, the data) is its own step; the environment is not a step. "
        "Give the expected and actual result on the step where the problem shows. Copy a "
        "cURL command exactly." + _LANGUAGE
    ),
)
async def rw_fill_field(
    key: Annotated[str, Field(description="The bug's key, e.g. BUG-42.")],
    field: Annotated[FillField, Field(description="Which field to fill.")],
    value: Annotated[
        list[StepInput] | EnvironmentInput | str,
        Field(description=(
            "Steps for reproduction_steps, a string for curl, an object for environment."
        )),
    ],
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        issue = await _item(db, user, key)
        if _value(issue.type) != IssueType.bug.value:
            raise ToolRefusal("bug_only", f"{_key(issue)} is a task; only bugs have these fields.")
        authorize(user, Action.edit_item, issue_target(issue, issue.project))
        if _value(issue.status) in _CLOSED:
            raise ToolRefusal(
                "item_closed",
                f"{_key(issue)} is {_value(issue.status).capitalize()}; its fields are final. "
                "Add a note instead.",
            )
        payload = _fill_payload(issue, field, value)
        issue = await issue_service.update(db, issue.id, payload, user)
        data = {"key": _key(issue), "field": field, "filled": sorted(payload)}
        return tool_result(data, f"Filled {field.replace('_', ' ')} on {data['key']}.")

    return await _run(build)


def _fill_payload(issue: Issue, field: str, value) -> dict:
    """The ``IssueService.update`` payload for one fill, after the emptiness rule
    (BR-M13). ``field_not_empty`` when the field — or, for the environment, any
    given sub-field — has a value."""
    def taken(what: str) -> ToolRefusal:
        return ToolRefusal(
            "field_not_empty",
            f"{_key(issue)} already has {what}; it is never overwritten. Add a note instead.",
        )

    def wrong(expected: str) -> ToolRefusal:
        return ToolRefusal("invalid_value", f"{field} takes {expected}.")

    if field == "reproduction_steps":
        if not isinstance(value, list) or not value:
            raise wrong("a non-empty list of steps")
        if issue.reproduction_steps:
            raise taken("reproduction steps")
        return {"reproduction_steps": _steps(value)}
    if field == "curl":
        if not isinstance(value, str) or not value.strip():
            raise wrong("a cURL command as a string")
        if issue.curl_command:
            raise taken("a cURL command")
        return {"curl_command": value.strip()}
    if not isinstance(value, EnvironmentInput) or not value.fields():
        raise wrong("an object with at least one of name, browser, os, build_hash, staging_url")
    given = value.fields()
    filled = [f for f in given if getattr(issue, f)]
    if filled:
        raise taken(", ".join(f.removeprefix("environment_").replace("_", " ") for f in filled))
    return given


# ── rw_report_recurrence (FR-M19) ─────────────────────────────────────────────


@server.tool(
    name="rw_report_recurrence",
    description=(
        "Report that the problem of an open or Cancelled bug happened again — only after the "
        "developer confirmed it is the same problem. The comment says what happened this "
        "time; it is public, like a recurrence from the web app, and has the same effects. "
        "Not allowed on Done items: file a new bug that names the Done item instead. "
        "Comment: one or two sentences on when and where it happened again (30–100 words), "
        "then an Evidence table with one row at minimum." + _EVIDENCE + _LANGUAGE
    ),
)
async def rw_report_recurrence(
    key: Annotated[str, Field(description="The bug's key, e.g. BUG-42.")],
    comment: Annotated[str, Field(min_length=1, description="What happened this time.")],
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        issue = await _item(db, user, key)
        if _value(issue.type) != IssueType.bug.value:
            raise ToolRefusal(
                "recurrence_not_allowed", f"{_key(issue)} is a task; only bugs recur.",
            )
        if _value(issue.status) == IssueStatus.done.value:
            raise ToolRefusal(
                "recurrence_not_allowed",
                f"{_key(issue)} is Done. File a new bug and name {_key(issue)} in its description.",
            )
        original = await recurrence_service.report(
            db, issue, RecurrenceCreate(comment=comment.strip()), user,
        )
        data = {
            "key": _key(original),
            "recurrence_count": original.recurrence_count,
            "status": _value(original.status),
        }
        return tool_result(
            data, f"Reported a recurrence on {data['key']} (now ×{data['recurrence_count']}).",
        )

    return await _run(build)


# ── Own content: rw_update_own, rw_delete_own (slice 18, FR-M25–M27) ─────────
# Agent ownership (``app/agent_ownership.py``) decides; the loader gathers the
# records. The edits and deletes then go through the same service paths as the UI.

_FIELD_TARGETS = {f"field:{name}": name for name in FIELDS}
_FIELD_COLUMNS = {
    "reproduction_steps": "reproduction steps", "curl": "cURL", "environment": "environment",
}


def _target(target: str, allowed: tuple[str, ...]) -> tuple[str, str | int | None]:
    """``(kind, detail)`` for a target string: ``("note", 12)``, ``("field", "curl")``,
    ``("title", None)``. ``invalid_target`` when it is not one of ``allowed``."""
    kind, _, rest = target.strip().partition(":")
    kind = kind.lower()
    if kind in ("note", "attachment") and kind in allowed and rest.strip().isdigit():
        return kind, int(rest)
    if kind == "field" and kind in allowed and f"field:{rest.strip()}" in _FIELD_TARGETS:
        return kind, rest.strip()
    if kind in ("title", "description") and kind in allowed and not rest:
        return kind, None
    shapes = {
        "note": "note:<id>", "attachment": "attachment:<id>",
        "field": "field:reproduction_steps|curl|environment",
        "title": "title", "description": "description",
    }
    raise ToolRefusal(
        "invalid_target",
        f"{target!r} is not a target. Use one of: {', '.join(shapes[a] for a in allowed)}.",
    )


def _owned(verdict) -> None:
    if not verdict.allowed:
        raise ToolRefusal(verdict.code, verdict.reason)


async def _note(db: AsyncSession, issue: Issue, note_id: int) -> IssueTimeline:
    note = (await db.execute(
        select(IssueTimeline).where(
            IssueTimeline.id == note_id, IssueTimeline.issue_id == issue.id,
            IssueTimeline.event_type == TimelineEventType.comment.value,
        )
    )).scalar_one_or_none()
    if note is None:
        raise ToolRefusal(
            "note_not_found",
            f"{_key(issue)} has no note {note_id}. Read its notes with rw_get_item.",
        )
    return note


async def _own_attachment(db: AsyncSession, issue: Issue, attachment_id: int) -> IssueAttachment:
    attachment = (await db.execute(
        select(IssueAttachment).where(
            IssueAttachment.id == attachment_id, IssueAttachment.issue_id == issue.id,
        )
    )).scalar_one_or_none()
    if attachment is None:
        raise ToolRefusal(
            "attachment_not_found",
            f"{_key(issue)} has no attachment {attachment_id}. "
            "Read its attachments with rw_get_item.",
        )
    return attachment


def _field_payload(field: str, value) -> dict:
    """The ``IssueService.update`` payload for an edit of a field the agent owns."""
    def wrong(expected: str) -> ToolRefusal:
        return ToolRefusal("invalid_value", f"field:{field} takes {expected}.")

    if field == "reproduction_steps":
        if not isinstance(value, list) or not value:
            raise wrong("a non-empty list of steps")
        return {"reproduction_steps": _steps(value)}
    if field == "curl":
        if not isinstance(value, str) or not value.strip():
            raise wrong("a cURL command as a string")
        return {"curl_command": value.strip()}
    if not isinstance(value, EnvironmentInput) or not value.fields():
        raise wrong("an object with at least one of name, browser, os, build_hash, staging_url")
    return value.fields()


def _text(value, target: str) -> str:
    if not isinstance(value, str):
        raise ToolRefusal("invalid_value", f"{target} takes a string.")
    return value


@server.tool(
    name="rw_update_own",
    description=(
        "Correct content your agent wrote and still owns: a note (note:<id>), a field you "
        "filled while the bug is not Done or Cancelled (field:reproduction_steps, "
        "field:curl, field:environment), or the title or description of an item you filed "
        "while the bug is New or the task is in the backlog. rw_get_item says per piece "
        "whether you may (you_can_edit). Once a person changes a piece in the UI, it is "
        "theirs: you get not_owner and add a note instead. The edit shows the edited "
        "marker. Same limits as on filing: title 15–90 characters, description 12,000, "
        "note 3,000." + _LANGUAGE
    ),
)
async def rw_update_own(
    key: Annotated[str, Field(description="The item's key, e.g. BUG-42.")],
    target: Annotated[str, Field(description=(
        "note:<id>, field:reproduction_steps, field:curl, field:environment, title, or "
        "description."
    ))],
    value: Annotated[
        list[StepInput] | EnvironmentInput | str,
        Field(description=(
            "The new value: text for a note, title, description or curl; steps for "
            "reproduction_steps; an object for environment (only the sub-fields you give change)."
        )),
    ],
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        issue = await _item(db, user, key)
        kind, detail = _target(target, ("note", "field", "title", "description"))
        ownership = await agent_ownership_loader.load(db, issue, user)

        if kind == "note":
            note = await _note(db, issue, detail)
            _owned(ownership.note(note))
            text = _text(value, "A note").strip()
            if not text:
                raise ToolRefusal("note_empty", "The note is empty.")
            if len(text) > NOTE_MAX:
                raise ToolRefusal(
                    "note_too_long",
                    f"The note has {len(text)} characters; the limit is {NOTE_MAX:,}. "
                    "Move long output to an attachment.",
                )
            await timeline_service.edit_comment(db, note.id, text, user)
            data = {"key": _key(issue), "target": f"note:{note.id}", "edited": True}
            return tool_result(data, f"Edited note {note.id} on {data['key']}.")

        authorize(user, Action.edit_item, issue_target(issue, issue.project))
        if kind == "field":
            if _value(issue.type) != IssueType.bug.value:
                raise ToolRefusal(
                    "bug_only", f"{_key(issue)} is a task; only bugs have these fields.",
                )
            _owned(ownership.field(detail))
            payload = _field_payload(detail, value)
            what = _FIELD_COLUMNS[detail]
        elif kind == "title":
            _owned(ownership.title())
            payload = {"title": _check_title(_text(value, "title"))}
            what = "the title"
        else:
            _owned(ownership.description())
            payload = {"description": _check_description(_text(value, "description"))}
            what = "the description"
        await issue_service.update(db, issue.id, payload, user)
        data = {"key": _key(issue), "target": target.strip(), "edited": True}
        return tool_result(data, f"Edited {what} of {data['key']}.")

    return await _run(build)


@server.tool(
    name="rw_delete_own",
    description=(
        "Delete a note (note:<id>) or an attachment (attachment:<id>) your agent created and "
        "still owns — for example a log from the wrong environment. rw_get_item says per "
        "note and attachment whether you may (you_can_edit). Once a person edits a note in "
        "the UI, it is theirs: you get not_owner. Deletion is final, as in the UI. To "
        "correct a note, prefer rw_update_own."
    ),
)
async def rw_delete_own(
    key: Annotated[str, Field(description="The item's key, e.g. BUG-42.")],
    target: Annotated[str, Field(description="note:<id> or attachment:<id>.")],
) -> CallToolResult:
    async def build(db: AsyncSession, user: User) -> CallToolResult:
        issue = await _item(db, user, key)
        kind, item_id = _target(target, ("note", "attachment"))
        ownership = await agent_ownership_loader.load(db, issue, user)
        if kind == "note":
            note = await _note(db, issue, item_id)
            _owned(ownership.note(note))
            await timeline_service.delete_comment(db, note, user)
        else:
            attachment = await _own_attachment(db, issue, item_id)
            _owned(ownership.attachment(attachment))
            authorize(user, Action.edit_item, issue_target(issue, issue.project))
            await attachment_service.delete(db, attachment, user)
        data = {"key": _key(issue), "target": f"{kind}:{item_id}", "deleted": True}
        return tool_result(data, f"Deleted {kind} {item_id} from {data['key']}.")

    return await _run(build)
