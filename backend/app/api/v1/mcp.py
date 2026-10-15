"""MCP tokens and the kill switch, for the UI (slice 15).

GET  /me/mcp                          — the profile's MCP section (tech users)
POST /me/mcp/tokens                   — create a token; the value is returned once
POST /me/mcp/tokens/{id}/revoke       — revoke an own token (404 for anyone else's)
GET  /settings/mcp                    — the switch and every user's tokens (CTO, Admin)
PUT  /settings/mcp                    — switch MCP on or off
POST /settings/mcp/tokens/{id}/revoke — revoke any user's token

There is no delete and no renewal endpoint (BR-M24, FR-M42).
"""

from datetime import datetime

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import get_now
from app.db.models.user import User
from app.db.session import get_db
from app.mcp_server.clients import CLIENTS, base_url, render_configs
from app.policy import Action
from app.schemas.mcp import (
    McpAdminTokenResponse,
    McpClientInfo,
    McpEnabledUpdate,
    McpProfileResponse,
    McpSettingsResponse,
    McpTokenCreate,
    McpTokenCreatedResponse,
    McpTokenResponse,
)
from app.services.authz import require_action
from app.services.mcp_token_service import is_enabled, mcp_token_service, set_enabled

router = APIRouter()

_CLIENTS = [
    McpClientInfo(
        key=c.key, name=c.name, supports_prompts=c.supports_prompts,
        supports_resources=c.supports_resources, where=c.where, language=c.language,
    )
    for c in CLIENTS
]


# ── Profile (FR-M38–M43) ──────────────────────────────────────────────────────


@router.get("/me/mcp", response_model=McpProfileResponse)
async def my_mcp(
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    current_user: User = Depends(require_action(Action.use_mcp)),
) -> McpProfileResponse:
    tokens = await mcp_token_service.list_for(db, current_user)
    return McpProfileResponse(
        enabled=await is_enabled(db),
        base_url=base_url(),
        clients=_CLIENTS,
        tokens=[McpTokenResponse.build(t, now) for t in tokens],
    )


@router.post(
    "/me/mcp/tokens", response_model=McpTokenCreatedResponse, status_code=status.HTTP_201_CREATED,
)
async def create_my_token(
    payload: McpTokenCreate,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    current_user: User = Depends(require_action(Action.use_mcp)),
) -> McpTokenCreatedResponse:
    token, value = await mcp_token_service.create(
        db, current_user, name=payload.name, lifetime_days=payload.lifetime_days, now=now,
    )
    await db.commit()
    return McpTokenCreatedResponse(
        token=McpTokenResponse.build(token, now), value=value, configs=render_configs(value),
    )


@router.post("/me/mcp/tokens/{token_id}/revoke", response_model=McpTokenResponse)
async def revoke_my_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    current_user: User = Depends(require_action(Action.use_mcp)),
) -> McpTokenResponse:
    token = await mcp_token_service.owned(db, current_user, token_id)
    await mcp_token_service.revoke(db, token, current_user, now)
    await db.commit()
    return McpTokenResponse.build(token, now)


# ── Settings → MCP (FR-M44) ───────────────────────────────────────────────────


async def _settings(db: AsyncSession, now: datetime) -> McpSettingsResponse:
    return McpSettingsResponse(
        enabled=await is_enabled(db),
        tokens=[McpAdminTokenResponse.build(t, now) for t in await mcp_token_service.list_all(db)],
    )


@router.get("/settings/mcp", response_model=McpSettingsResponse)
async def get_mcp_settings(
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    _: User = Depends(require_action(Action.manage_mcp_tokens)),
) -> McpSettingsResponse:
    return await _settings(db, now)


@router.put("/settings/mcp", response_model=McpSettingsResponse)
async def put_mcp_settings(
    payload: McpEnabledUpdate,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    _: User = Depends(require_action(Action.manage_mcp_tokens)),
) -> McpSettingsResponse:
    await set_enabled(db, payload.enabled)
    return await _settings(db, now)


@router.post("/settings/mcp/tokens/{token_id}/revoke", response_model=McpAdminTokenResponse)
async def revoke_any_token(
    token_id: int,
    db: AsyncSession = Depends(get_db),
    now: datetime = Depends(get_now),
    current_user: User = Depends(require_action(Action.manage_mcp_tokens)),
) -> McpAdminTokenResponse:
    token = await mcp_token_service.by_id(db, token_id)
    await mcp_token_service.revoke(db, token, current_user, now)
    await db.commit()
    await db.refresh(token, ["user"])
    return McpAdminTokenResponse.build(token, now)
