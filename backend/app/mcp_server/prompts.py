"""The MCP prompts and the writing-standard resource (slice 18, prd-mcp.md FR-M33–FR-M37).

Three prompts encode the working method: ``rw-next``, ``rw-work <key>`` and
``rw-report``. Their text is product content, one file per prompt in
``content/``, versioned with the code and the same for every installation
(FR-M37). Every prompt ends with the shared boundaries (``content/boundaries.md``).

``content/agent-writing-standard.md`` is the single source of the Agent Writing
Standard (``docs/phase-2/agent-writing-standard.md`` links to it). It is served
as ``rw://standards/writing``, and ``rw-work`` and ``rw-report`` embed it, so an
agent has it even when its client does not read resources. Every file is read
once, when the server starts.
"""

from pathlib import Path
from typing import Annotated

from mcp.server.mcpserver.prompts.base import UserMessage
from mcp.types import EmbeddedResource, TextResourceContents
from pydantic import Field

from app.mcp_server.server import server

_CONTENT = Path(__file__).parent / "content"
STANDARD_URI = "rw://standards/writing"


def _read(name: str) -> str:
    return (_CONTENT / name).read_text(encoding="utf-8").strip()


STANDARD = _read("agent-writing-standard.md")
_BOUNDARIES = _read("boundaries.md")
_NEXT = _read("rw-next.md")
_WORK = _read("rw-work.md")
_REPORT = _read("rw-report.md")


def _with_boundaries(text: str) -> str:
    return f"{text}\n\n{_BOUNDARIES}\n"


def _standard_message() -> UserMessage:
    return UserMessage(EmbeddedResource(
        type="resource",
        resource=TextResourceContents(uri=STANDARD_URI, mime_type="text/markdown", text=STANDARD),
    ))


@server.resource(
    STANDARD_URI,
    name="writing-standard",
    title="Agent Writing Standard",
    description=(
        "How an agent writes in Releasewatch: English in ASD-STE100, the templates for bugs, "
        "technical debt, notes and recurrences, the evidence and attachment rules, and the "
        "length limits."
    ),
    mime_type="text/markdown",
)
def writing_standard() -> str:
    return STANDARD


@server.prompt(
    name="rw-next",
    title="Next Releasewatch item",
    description=(
        "Load your next item — the first In progress item, or else the first in your queue — "
        "with its full context and images. Reminds you to move its status in Releasewatch."
    ),
)
def rw_next() -> list[UserMessage]:
    return [UserMessage(_with_boundaries(_NEXT))]


@server.prompt(
    name="rw-work",
    title="Work on a Releasewatch item",
    description=(
        "Load one item's full context; a Rejected item starts from the reject comment. Adds the "
        "PR link as a note when you open a PR."
    ),
)
def rw_work(
    key: Annotated[str, Field(description="The item's key, e.g. BUG-42 or TASK-118.")],
) -> list[UserMessage]:
    text = _WORK.replace("{key}", key.strip().upper())
    return [UserMessage(_with_boundaries(text)), _standard_message()]


@server.prompt(
    name="rw-report",
    title="Report to Releasewatch",
    description=(
        "Report a bug or technical debt by the Agent Writing Standard: gather evidence, decide "
        "the type with you, show the draft, check duplicates, and file only when you agree."
    ),
)
def rw_report() -> list[UserMessage]:
    return [UserMessage(_with_boundaries(_REPORT)), _standard_message()]
