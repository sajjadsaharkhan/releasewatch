"""Authentication schemas."""

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credentials supplied to POST /auth/login."""

    username: str
    password: str = Field(min_length=8)


class TokenResponse(BaseModel):
    """JWT pair returned after a successful login or token refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """Payload for POST /auth/refresh."""

    refresh_token: str


class TelegramTokenResponse(BaseModel):
    """One-time connect token for linking a Telegram account."""

    connect_token: str
    expires_at: str  # ISO-8601 datetime string


class UserMeResponse(BaseModel):
    """Authenticated user summary returned by GET /auth/me."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    username: str
    role: str
    avatar_color: str
    avatar_url: str | None = None
    is_active: bool


class TelegramIntegrationResponse(BaseModel):
    """Telegram bot integration status for GET /settings/integrations/telegram."""

    bot_username: str
    connected_count: int
    bot_token_set: bool = False
    bot_token_preview: str | None = None
    # Live bot info from getMe (populated when token is set)
    bot_id: int | None = None
    bot_first_name: str | None = None
    # Connectivity test result
    connectivity_ok: bool | None = None   # None = no token to test
    via_proxy: bool = False
    proxy_url_preview: str | None = None
    connectivity_error: str | None = None


class TelegramStatusResponse(BaseModel):
    """Per-user Telegram connection state returned by GET /auth/me/telegram."""

    connected: bool
    telegram_username: str | None = None
    telegram_full_name: str | None = None
    telegram_user_id: int | None = None
    connected_at: str | None = None
    last_event_sent_at: str | None = None
    token: str | None = None
    token_expires_at: str | None = None
