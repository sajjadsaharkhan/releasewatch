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
    telegram_handle: str | None = None
    telegram_connected_at: str | None = None
    is_active: bool


class TelegramIntegrationResponse(BaseModel):
    """Telegram bot integration status for GET /settings/integrations/telegram."""

    bot_username: str
    connected_count: int
