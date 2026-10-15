"""What an MCP tool hands back (slice 16, prd-mcp.md A.8).

A tool answers with structured content (JSON) plus a short Markdown rendering
of the same structure as its text, so a client that shows only text still
reads well. A failure the agent should relay is an MCP tool error carrying
``{code, message}`` — never an HTTP error, never a traceback.
"""

from typing import Any

from mcp.types import CallToolResult, ContentBlock, TextContent
from pydantic_core import to_jsonable_python


class ToolRefusal(Exception):
    """A tool refused the call: ``code`` is stable, ``message`` is one sentence.
    ``data`` adds fields to the structured error (``duplicates_found`` carries
    its candidates) and ``markdown`` follows the message in the text."""

    def __init__(
        self, code: str, message: str, *, data: dict[str, Any] | None = None,
        markdown: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data or {}
        self.markdown = markdown


def not_found(what: str) -> ToolRefusal:
    """``not_found`` — unknown and invisible look the same (BR-M03, AC-M03)."""
    return ToolRefusal("not_found", f"{what} was not found, or you cannot see it.")


def tool_result(data: dict[str, Any], markdown: str, *blocks: ContentBlock) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=markdown), *blocks],
        structured_content=to_jsonable_python(data),
    )


def error_result(refusal: ToolRefusal) -> CallToolResult:
    text = refusal.message + (f"\n\n{refusal.markdown}" if refusal.markdown else "")
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content=to_jsonable_python(
            {**refusal.data, "code": refusal.code, "message": refusal.message},
        ),
        is_error=True,
    )
