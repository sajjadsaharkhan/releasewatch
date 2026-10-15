"""Agent context (slice 17, prd-mcp.md A.4): which MCP token the current request acts through.

``McpEndpoint`` is the only code that sets it, for the duration of one ``/mcp``
request. Three writers read it and stamp ``via_mcp_token_id`` on what they
create — ``TimelineService.create_event``, ``IssueService.create`` and
``AttachmentService.add`` — so every row an agent action writes, side effects
included, is agent content (BR-M05). Web requests, Celery tasks and the
Telegram bot never set it, so they write ``NULL``.
"""

import contextvars

agent_token_id: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "agent_token_id", default=None,
)


def current_agent_token_id() -> int | None:
    """The MCP token of the current request, or ``None`` outside ``/mcp``."""
    return agent_token_id.get()
