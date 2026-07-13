"""Settings API — notification preferences and integrations."""

import asyncio
import logging
from urllib.parse import urlparse, urlunparse
import httpx
from sqlalchemy import select, func
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.core.auth import get_current_user, require_role
from app.db.models.telegram_integration import TelegramIntegration
from app.db.models.user import User, UserRole
from app.db.models.system_setting import SystemSetting
from app.db.session import get_db
from app.schemas.auth import TelegramIntegrationResponse
from app.schemas.settings import (
    ProxyConfig,
    LLMConfig,
    GeneralConfig,
    GeneralResponse,
    ConfigurationResponse,
    LLMTestRequest,
    LLMTestResponse,
    TelegramBotConfigRequest,
)

router = APIRouter()

# In production these would be stored per-user/workspace in a settings table.
# For now they are returned as a default matrix and accepted as-is.

from app.core.notification_defaults import DEFAULT_NOTIFICATION_MATRIX as _DEFAULT_NOTIFICATION_MATRIX

_gitlab_config: dict = {}


@router.get("/notifications")
async def get_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the notification preference matrix (event types × roles)."""
    stored = await _get_setting(db, "notifications", "matrix")
    matrix = dict(_DEFAULT_NOTIFICATION_MATRIX)
    if stored:
        matrix.update(stored)
    return matrix


@router.put("/notifications")
async def save_notifications(
    body: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Persist notification preferences. Body must match the matrix shape."""
    current = await _get_setting(db, "notifications", "matrix") or dict(_DEFAULT_NOTIFICATION_MATRIX)
    current.update(body)
    await _set_setting(db, "notifications", "matrix", current)
    return current


@router.get("/integrations/gitlab")
async def get_gitlab_config(
    current_user: User = Depends(get_current_user),
):
    """Return GitLab webhook connection status and config."""
    return {
        "connected": bool(_gitlab_config.get("webhook_url")),
        "webhook_url": _gitlab_config.get("webhook_url"),
        "target_branch": _gitlab_config.get("target_branch", "main"),
    }


@router.post("/integrations/gitlab")
async def save_gitlab_config(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Save GitLab webhook URL, secret, and target branch."""
    _gitlab_config.update(body)
    return {"connected": True, **_gitlab_config}


def _mask_bot_token(token: str) -> str:
    """Return a partially-masked token preview for display."""
    if ":" not in token:
        return token[:4] + "..." if len(token) > 4 else "***"
    bot_id, key = token.split(":", 1)
    return bot_id + ":" + key[:4] + "..." + key[-4:]


def _mask_proxy_url(url: str) -> str:
    """Mask credentials in a proxy URL so it is safe to return to the frontend."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            host = f"{parsed.hostname}:{parsed.port}" if parsed.port else (parsed.hostname or "")
            netloc = f"{parsed.username}:***@{host}" if parsed.username else f"***@{host}"
            return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        pass
    return url


async def _call_get_me(token: str, proxy_url: str | None) -> tuple[dict | None, str | None]:
    """Call Telegram getMe with a 5-second timeout. Returns (bot_info_dict, error_str)."""
    from app.telegram.client import TelegramClient, TelegramAPIError
    client = TelegramClient(token=token, proxy_url=proxy_url)
    try:
        r = await asyncio.wait_for(
            client._http.post(f"https://api.telegram.org/bot{token}/getMe"),
            timeout=5.0,
        )
        r.raise_for_status()
        data = r.json()
        if not data.get("ok"):
            return None, data.get("description", "getMe returned ok=false")
        return data["result"], None
    except asyncio.TimeoutError:
        return None, "Request timed out (5 s)"
    except Exception as exc:
        return None, str(exc)
    finally:
        await client.close()


@router.get("/integrations/telegram", response_model=TelegramIntegrationResponse)
async def get_telegram_integration(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return Telegram bot status including live getMe result and connectivity state."""
    result = await db.execute(
        select(func.count(TelegramIntegration.id)).where(
            TelegramIntegration.is_active.is_(True)
        )
    )
    connected_count = result.scalar_one()

    tg_config = await _get_setting(db, "telegram", "config")
    stored_token = tg_config.get("bot_token") if tg_config else None
    stored_username = tg_config.get("bot_username") if tg_config else None

    if not stored_token:
        return TelegramIntegrationResponse(
            bot_username="Bot not configured",
            connected_count=connected_count,
            bot_token_set=False,
        )

    # Read proxy config
    proxy_val = await _get_setting(db, "proxy", "config")
    proxy_url: str | None = None
    via_proxy = False
    if proxy_val and proxy_val.get("enabled"):
        proxy_url = proxy_val.get("http") or proxy_val.get("https") or None
        via_proxy = bool(proxy_url)

    # Live getMe call
    bot_info, error = await _call_get_me(stored_token, proxy_url)

    if bot_info:
        # Update stored username/id if they changed
        updated_username = f"@{bot_info['username']}"
        if updated_username != stored_username or not tg_config.get("bot_id"):
            tg_config["bot_username"] = updated_username
            tg_config["bot_id"] = bot_info["id"]
            tg_config["bot_first_name"] = bot_info.get("first_name")
            await _set_setting(db, "telegram", "config", tg_config)

    return TelegramIntegrationResponse(
        bot_username=(f"@{bot_info['username']}" if bot_info else None) or stored_username or "Unknown",
        connected_count=connected_count,
        bot_token_set=True,
        bot_token_preview=_mask_bot_token(stored_token),
        bot_id=bot_info["id"] if bot_info else tg_config.get("bot_id"),
        bot_first_name=bot_info.get("first_name") if bot_info else tg_config.get("bot_first_name"),
        connectivity_ok=bot_info is not None,
        via_proxy=via_proxy,
        proxy_url_preview=_mask_proxy_url(proxy_url) if proxy_url else None,
        connectivity_error=error,
        frontend_url=tg_config.get("frontend_url"),
    )


@router.put("/integrations/telegram", response_model=TelegramIntegrationResponse)
async def save_telegram_integration(
    body: TelegramBotConfigRequest,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    """Save Telegram bot token (admin only).

    After storing the token, calls Telegram getMe to auto-populate the bot username.
    Restart the backend for the new token to take effect in the polling loop.
    """
    existing = await _get_setting(db, "telegram", "config") or {}

    if body.bot_token is not None:
        existing["bot_token"] = body.bot_token
        # Auto-fetch bot username from Telegram getMe API
        try:
            proxy_val = await _get_setting(db, "proxy", "config")
            proxy_url = None
            if proxy_val and proxy_val.get("enabled"):
                proxy_url = proxy_val.get("socks5") or proxy_val.get("http") or proxy_val.get("https")
            bot_info, _ = await _call_get_me(body.bot_token, proxy_url)
            if bot_info:
                existing["bot_username"] = f"@{bot_info['username']}"
                existing["bot_id"] = bot_info["id"]
                existing["bot_first_name"] = bot_info.get("first_name")
                logger.info("Bot identity confirmed: %s (id=%s)", bot_info["username"], bot_info["id"])
        except Exception as exc:
            logger.warning("Could not fetch bot info via getMe (token saved anyway): %s", exc)

    if body.bot_username is not None:
        existing["bot_username"] = body.bot_username

    if body.frontend_url is not None:
        existing["frontend_url"] = body.frontend_url.rstrip("/")

    await _set_setting(db, "telegram", "config", existing)

    stored_token = existing.get("bot_token")
    connected_count = (
        await db.execute(
            select(func.count(TelegramIntegration.id)).where(
                TelegramIntegration.is_active.is_(True)
            )
        )
    ).scalar_one()

    return TelegramIntegrationResponse(
        bot_username=existing.get("bot_username") or "Bot not configured",
        connected_count=connected_count,
        bot_token_set=bool(stored_token),
        bot_token_preview=_mask_bot_token(stored_token) if stored_token else None,
        frontend_url=existing.get("frontend_url"),
    )


# ─── General Settings (Workspace & Timezone) ─────────────────────────────────────


@router.get("/general", response_model=GeneralResponse)
async def get_general_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get general workspace settings."""
    # Get general settings from database
    general_value = await _get_setting(db, "general", "config")
    general_config = GeneralConfig(**general_value) if general_value else GeneralConfig()

    return {
        "general": general_config.model_dump(by_alias=True),
    }


@router.put("/general")
async def save_general_settings(
    body: GeneralConfig,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    """Save general workspace settings (admin only)."""
    await _set_setting(
        db,
        "general",
        "config",
        {
            "workspace": body.workspace,
            "timezone": body.timezone,
        },
    )

    return {"status": "ok"}


# ─── Configuration (Proxy & LLM) ────────────────────────────────────────────────


async def _get_setting(db: AsyncSession, category: str, key: str) -> dict | None:
    """Get a setting value from the database."""
    result = await db.execute(
        select(SystemSetting)
        .where(SystemSetting.category == category)
        .where(SystemSetting.key == key)
        .where(SystemSetting.is_active == True)
    )
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def _set_setting(db: AsyncSession, category: str, key: str, value: dict) -> None:
    """Set a setting value in the database (upsert).

    Always uses a fresh dict copy + flag_modified so SQLAlchemy detects the
    change even when the caller mutated the same dict object that came from the DB.
    JSONB columns are not mutation-tracked by default.
    """
    from sqlalchemy.orm import attributes as sa_attrs

    result = await db.execute(
        select(SystemSetting)
        .where(SystemSetting.category == category)
        .where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = dict(value)          # new object — avoids same-reference no-op
        sa_attrs.flag_modified(setting, "value")  # force dirty even if ORM disagrees
    else:
        setting = SystemSetting(category=category, key=key, value=dict(value))
        db.add(setting)

    await db.commit()


@router.get("/configuration")
async def get_configuration(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get system configuration (proxy and LLM settings)."""
    # Get proxy settings
    proxy_value = await _get_setting(db, "proxy", "config")
    proxy_config = ProxyConfig(**proxy_value) if proxy_value else ProxyConfig()

    # Get LLM settings
    llm_value = await _get_setting(db, "llm", "config")
    if llm_value:
        llm_config = LLMConfig(
            embedding_provider=llm_value.get("embedding_provider", "local"),
            local_model=llm_value.get("local_model", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
            base_url=llm_value.get("base_url", ""),
            api_key=llm_value.get("api_key", ""),
            embedding_model=llm_value.get("embedding_model", ""),
            embedding_dimension=llm_value.get("embedding_dimension", 384),
            rerank_enabled=llm_value.get("rerank_enabled", False),
        )
    else:
        llm_config = LLMConfig()

    # Return with camelCase aliases for frontend
    return {
        "proxy": proxy_config.model_dump(by_alias=True),
        "llm": llm_config.model_dump(by_alias=True),
    }


@router.put("/configuration")
async def save_configuration(
    body: ConfigurationResponse,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
):
    """Save system configuration (admin only)."""
    # Save proxy settings
    await _set_setting(
        db,
        "proxy",
        "config",
        {
            "enabled": body.proxy.enabled,
            "http": body.proxy.http,
            "https": body.proxy.https,
            "no_proxy": body.proxy.no_proxy,
        },
    )

    # Save LLM settings
    await _set_setting(
        db,
        "llm",
        "config",
        {
            "embedding_provider": body.llm.embedding_provider,
            "local_model": body.llm.local_model,
            "base_url": body.llm.base_url,
            "api_key": body.llm.api_key,
            "embedding_model": body.llm.embedding_model,
            "embedding_dimension": body.llm.embedding_dimension,
            "rerank_enabled": body.llm.rerank_enabled,
        },
    )

    return {"status": "ok"}


@router.post("/configuration/llm/test")
async def test_llm_connection(
    body: LLMTestRequest,
    current_user: User = Depends(require_role(UserRole.admin)),
):
    """Test LLM provider connection (admin only).

    Tries multiple endpoint patterns to accommodate different LLM providers:
    - /models endpoint (OpenAI-compatible)
    - /v1/models endpoint (some providers)
    - Base URL itself (health check endpoints)
    """
    headers = {"Authorization": f"Bearer {body.api_key}"}
    base = body.base_url.rstrip('/')

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try 1: /models endpoint (most common)
            try:
                response = await client.get(f"{base}/models", headers=headers)
                if response.status_code == 200:
                    return LLMTestResponse(
                        success=True,
                        message="Successfully connected to LLM provider",
                    )
                elif response.status_code == 401:
                    return LLMTestResponse(
                        success=False,
                        message="Authentication failed: Invalid API key",
                    )
            except Exception:
                pass  # Try next pattern

            # Try 2: Base URL directly (for providers with health endpoints at root)
            try:
                response = await client.get(base, headers=headers)
                if response.status_code == 200:
                    return LLMTestResponse(
                        success=True,
                        message="Successfully connected to LLM provider (base URL)",
                    )
            except Exception:
                pass  # Try next pattern

            # Try 3: /v1/models if base doesn't already end with /v1
            if not base.endswith('/v1'):
                try:
                    response = await client.get(f"{base}/v1/models", headers=headers)
                    if response.status_code == 200:
                        return LLMTestResponse(
                            success=True,
                            message="Successfully connected to LLM provider",
                        )
                    elif response.status_code == 401:
                        return LLMTestResponse(
                            success=False,
                            message="Authentication failed: Invalid API key",
                        )
                except Exception:
                    pass

            # All attempts failed
            return LLMTestResponse(
                success=False,
                message="Connection failed: Unable to reach any known LLM endpoint",
            )

    except httpx.ConnectError:
        return LLMTestResponse(
            success=False,
            message="Connection failed: Unable to reach the server",
        )
    except httpx.TimeoutException:
        return LLMTestResponse(
            success=False,
            message="Connection failed: Request timed out",
        )
    except Exception as e:
        return LLMTestResponse(
            success=False,
            message=f"Connection failed: {str(e)}",
        )
