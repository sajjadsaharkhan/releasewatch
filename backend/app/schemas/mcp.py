"""MCP token schemas (slice 15, docs/phase-2/15-mcp-connection-and-tokens.md).

No response model carries the token value or its hash, except
``McpTokenCreatedResponse.value`` — returned once, by create (BR-M21).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.db.models.mcp_token import (
    MCP_TOKEN_DEFAULT_LIFETIME_DAYS,
    MCP_TOKEN_LIFETIME_DAYS,
    McpToken,
    McpTokenStatus,
)

Lifetime = Literal[*MCP_TOKEN_LIFETIME_DAYS]  # type: ignore[valid-type]


class McpTokenCreate(BaseModel):
    name: str = Field(max_length=64)
    lifetime_days: Lifetime = MCP_TOKEN_DEFAULT_LIFETIME_DAYS  # type: ignore[valid-type]

    @field_validator("name")
    @classmethod
    def _name_required(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name is required.")
        return v


class McpEnabledUpdate(BaseModel):
    enabled: bool


class McpTokenOwner(BaseModel):
    id: int
    name: str
    username: str
    avatar_color: str | None = None
    avatar_url: str | None = None


class McpTokenResponse(BaseModel):
    id: int
    name: str
    token_prefix: str
    created_at: datetime
    expires_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    status: McpTokenStatus

    @classmethod
    def build(cls, token: McpToken, now: datetime) -> "McpTokenResponse":
        return cls(
            id=token.id, name=token.name, token_prefix=token.token_prefix,
            created_at=token.created_at, expires_at=token.expires_at,
            last_used_at=token.last_used_at, revoked_at=token.revoked_at,
            status=token.status_at(now),
        )


class McpAdminTokenResponse(McpTokenResponse):
    user: McpTokenOwner

    @classmethod
    def build(cls, token: McpToken, now: datetime) -> "McpAdminTokenResponse":
        base = McpTokenResponse.build(token, now).model_dump()
        u = token.user
        return cls(**base, user=McpTokenOwner(
            id=u.id, name=u.name, username=u.username,
            avatar_color=u.avatar_color, avatar_url=u.avatar_url,
        ))


class McpClientInfo(BaseModel):
    key: str
    name: str
    supports_prompts: bool
    supports_resources: bool
    #: Where the configuration goes, in one line ("Run in a terminal", "~/.codex/config.toml").
    where: str
    #: The syntax of the rendered configuration, for highlighting: shell | toml | json.
    language: str


class McpProfileResponse(BaseModel):
    enabled: bool
    base_url: str
    clients: list[McpClientInfo]
    tokens: list[McpTokenResponse]


class McpTokenCreatedResponse(BaseModel):
    token: McpTokenResponse
    #: The token value — shown once, never again (BR-M21).
    value: str
    #: One ready configuration per client key, with the base URL and the value in it.
    configs: dict[str, str]


class McpSettingsResponse(BaseModel):
    enabled: bool
    tokens: list[McpAdminTokenResponse]
