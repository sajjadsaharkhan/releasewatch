"""The coding agents the profile's MCP section configures (slice 15, FR-M41).

Product content, declared once: each client's name, whether it supports MCP
prompts and resources (the guide says when it doesn't), and the one template
its ready-to-copy configuration is rendered from. The UI never assembles a
configuration — it shows what ``render_configs`` returns.
"""

from dataclasses import dataclass

from app.config import settings

#: The server name every configuration registers.
SERVER_NAME = "releasewatch"


@dataclass(frozen=True)
class McpClient:
    key: str
    name: str
    #: False also where the client's docs don't say (ZCode, checked 2026-10-15):
    #: the guide promises only what is documented.
    supports_prompts: bool
    supports_resources: bool
    where: str
    language: str
    template: str


CLIENTS: tuple[McpClient, ...] = (
    McpClient(
        key="claude_code",
        name="Claude Code",
        supports_prompts=True,
        supports_resources=True,
        where="Run in a terminal",
        language="shell",
        template=(
            "claude mcp add --transport http {server} {base_url} \\\n"
            '  --header "Authorization: Bearer {token}"'
        ),
    ),
    McpClient(
        key="codex",
        name="Codex",
        # openai/codex#5059: no MCP prompts; the model reads resources itself.
        supports_prompts=False,
        supports_resources=True,
        where="Add to ~/.codex/config.toml",
        language="toml",
        template=(
            "[mcp_servers.{server}]\n"
            'url = "{base_url}"\n'
            'http_headers = {{ "Authorization" = "Bearer {token}" }}'
        ),
    ),
    McpClient(
        key="zcode",
        name="ZCode",
        supports_prompts=False,
        supports_resources=False,
        where="In ZCode: Settings → MCP Servers → New MCP Server, paste as JSON",
        language="json",
        template=(
            "{{\n"
            '  "mcpServers": {{\n'
            '    "{server}": {{\n'
            '      "type": "http",\n'
            '      "url": "{base_url}",\n'
            '      "headers": {{ "Authorization": "Bearer {token}" }}\n'
            "    }}\n"
            "  }}\n"
            "}}"
        ),
    ),
)


def base_url() -> str:
    """The public app URL plus ``/mcp`` — what every client connects to."""
    return settings.FRONTEND_URL.rstrip("/") + "/mcp"


def render_configs(token: str) -> dict[str, str]:
    """One ready configuration per client, with the base URL and ``token`` in it."""
    url = base_url()
    return {
        c.key: c.template.format(server=SERVER_NAME, base_url=url, token=token) for c in CLIENTS
    }
