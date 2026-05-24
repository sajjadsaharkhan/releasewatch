"""Settings API — notification preferences and integrations."""

import httpx
from sqlalchemy import select, func
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_role
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
)

router = APIRouter()

# In production these would be stored per-user/workspace in a settings table.
# For now they are returned as a default matrix and accepted as-is.

_DEFAULT_NOTIFICATION_MATRIX = {
    "filed": {"reporter": True, "assignee": False, "triage": True, "cto": True},
    "assigned": {"reporter": False, "assignee": True, "triage": False, "cto": False},
    "comment": {"reporter": True, "assignee": True, "triage": False, "cto": False},
    "mention": {"reporter": True, "assignee": True, "triage": True, "cto": True},
    "regression": {"reporter": True, "assignee": True, "triage": True, "cto": True},
    "fix_ready": {"reporter": True, "assignee": False, "triage": False, "cto": False},
    "fix_verified": {"reporter": False, "assignee": True, "triage": False, "cto": False},
    "release_gate": {"reporter": False, "assignee": False, "triage": True, "cto": True},
}

_gitlab_config: dict = {}


@router.get("/notifications")
async def get_notifications(
    current_user: User = Depends(get_current_user),
):
    """Return the notification preference matrix (event types × roles)."""
    return _DEFAULT_NOTIFICATION_MATRIX


@router.put("/notifications")
async def save_notifications(
    body: dict,
    current_user: User = Depends(get_current_user),
):
    """Persist notification preferences. Body must match the matrix shape."""
    _DEFAULT_NOTIFICATION_MATRIX.update(body)
    return _DEFAULT_NOTIFICATION_MATRIX


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


@router.get("/integrations/telegram", response_model=TelegramIntegrationResponse)
async def get_telegram_integration(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return Telegram bot integration status and connected member count."""
    # Count users with connected Telegram accounts
    result = await db.execute(
        select(func.count(User.id)).where(User.telegram_handle.is_not(None))
    )
    connected_count = result.scalar_one()

    return TelegramIntegrationResponse(
        bot_username="@ReleasewatchBot",
        connected_count=connected_count,
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
    """Set a setting value in the database (upsert)."""
    result = await db.execute(
        select(SystemSetting)
        .where(SystemSetting.category == category)
        .where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting:
        setting.value = value
    else:
        setting = SystemSetting(category=category, key=key, value=value)
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
            base_url=llm_value.get("base_url", ""),
            api_key=llm_value.get("api_key", ""),
            embedding_model=llm_value.get("embedding_model", ""),
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
            "base_url": body.llm.base_url,
            "api_key": body.llm.api_key,
            "embedding_model": body.llm.embedding_model,
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
