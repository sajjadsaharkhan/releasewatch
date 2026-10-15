"""The ``/mcp`` endpoint: the auth gate and the tools (slice 15, prd-mcp.md A.1).

``McpEndpoint`` is the ASGI app FastAPI routes ``/mcp`` to. Per request it
resolves ``Authorization: Bearer rwm_…`` through ``McpTokenService`` (the
"MCP auth dependency" of the spec), then hands the request to the SDK's
stateless streamable-HTTP transport with the principal set in a context
variable. A refusal before any tool runs is an HTTP error carrying a JSON-RPC
error body, so clients relay its message. Once authenticated, tool errors are
MCP tool errors with ``{code, message}`` (A.8), never HTTP errors — slice 15's
one tool has none.

Each request gets its own session manager: the server is stateless, and a
manager per request needs no long-lived task group in the app's lifespan (or
in the test harness, which never runs it).
"""

import contextvars
import inspect
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.mcpserver import MCPServer
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.config import settings
from app.core.clock import get_now
from app.db.models.project import Project
from app.db.models.user import User
from app.db.session import get_db
from app.mcp_server.clients import SERVER_NAME
from app.services.mcp_token_service import McpRefusal, mcp_token_service

# The SDK logs every per-request manager start/stop at INFO.
logging.getLogger("mcp.server.streamable_http_manager").setLevel(logging.WARNING)

db_session = asynccontextmanager(get_db)


@dataclass(frozen=True)
class McpPrincipal:
    """Who the request acts as (BR-M03) and through which token."""

    user_id: int
    token_id: int


#: Set only by ``McpEndpoint`` for the duration of one ``/mcp`` request.
current_principal: contextvars.ContextVar[McpPrincipal | None] = contextvars.ContextVar(
    "mcp_principal", default=None,
)


async def principal_user(db: AsyncSession) -> User:
    """The token's owner — every tool acts as this user (BR-M03)."""
    principal = current_principal.get()
    if principal is None:
        raise RuntimeError("An MCP tool ran outside McpEndpoint.")
    return await db.get_one(User, principal.user_id)


# ── Server and tools ──────────────────────────────────────────────────────────

server = MCPServer(
    SERVER_NAME,
    title="Releasewatch",
    version=settings.APP_VERSION,
    instructions=(
        "Releasewatch is the team's release-scoped QA tracker. Call rw_context first: "
        "it says who you act as and which projects you can see."
    ),
)


class ContextUser(BaseModel):
    name: str
    username: str
    role: str


class ContextProject(BaseModel):
    key: str
    name: str


class ContextResult(BaseModel):
    user: ContextUser
    projects: list[ContextProject]
    jev_enabled: bool


@server.tool(
    name="rw_context",
    description=(
        "Who you act as in Releasewatch (name, username, role), the projects you can see "
        "(key and name), and whether Jev — the AI duplicate check — is enabled. "
        "Call this first."
    ),
)
async def rw_context() -> ContextResult:
    from app.search import jev_settings

    async with db_session() as db:
        user = await principal_user(db)
        # Tech roles see every project (BR-30, BR-M03); archived ones take no work.
        projects = (await db.execute(
            select(Project).where(Project.archived_at.is_(None)).order_by(Project.name)
        )).scalars().all()
        return ContextResult(
            user=ContextUser(
                name=user.name, username=user.username,
                role=getattr(user.role, "value", user.role),
            ),
            projects=[ContextProject(key=p.slug, name=p.name) for p in projects],
            jev_enabled=await jev_settings.is_enabled(db),
        )


# ── The endpoint ──────────────────────────────────────────────────────────────

#: The bearer token is the protection here, not the Host header: DNS-rebinding
#: checks would refuse every non-localhost deployment.
_TRANSPORT_SECURITY = TransportSecuritySettings(enable_dns_rebinding_protection=False)
#: JSON-RPC "server error" range — the refusal before any tool runs.
_REFUSED = -32001


def _bearer(scope: Scope) -> str | None:
    for key, value in scope.get("headers", []):
        if key == b"authorization":
            scheme, _, credentials = value.decode("latin-1").partition(" ")
            return credentials.strip() if scheme.lower() == "bearer" else None
    return None


class McpEndpoint:
    """ASGI app for ``/mcp``: authenticate, then serve one stateless MCP request."""

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # The clock seam (01-test-harness §Clock): honour a ``get_now`` override
        # the way a FastAPI route would, since this endpoint isn't one.
        app = scope.get("app")
        now_fn = getattr(app, "dependency_overrides", {}).get(get_now, get_now)
        now = await now_fn() if inspect.iscoroutinefunction(now_fn) else now_fn()
        try:
            async with db_session() as db:
                user, token = await mcp_token_service.resolve(db, _bearer(scope), now)
                await mcp_token_service.touch(db, token, now)
                principal = McpPrincipal(user_id=user.id, token_id=token.id)
        except McpRefusal as refusal:
            await JSONResponse(
                {
                    "jsonrpc": "2.0", "id": None,
                    "error": {
                        "code": _REFUSED, "message": refusal.message,
                        "data": {"code": refusal.code},
                    },
                },
                status_code=refusal.http_status,
                headers={"WWW-Authenticate": "Bearer"} if refusal.http_status == 401 else None,
            )(scope, receive, send)
            return

        reset = current_principal.set(principal)
        try:
            manager = StreamableHTTPSessionManager(
                app=server._lowlevel_server,  # the SDK's own accessor is private too
                stateless=True,
                json_response=True,
                security_settings=_TRANSPORT_SECURITY,
            )
            async with manager.run():
                await manager.handle_request(scope, receive, send)
        finally:
            current_principal.reset(reset)


mcp_endpoint = McpEndpoint()
