"""Settings schemas — for system configuration (proxy, general, Telegram)."""

from pydantic import BaseModel, ConfigDict, Field


class GeneralConfig(BaseModel):
    """General workspace configuration."""

    workspace: str = Field(default="Releasewatch", alias="workspaceName")
    timezone: str = Field(default="UTC")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class ProxyConfig(BaseModel):
    """HTTP proxy configuration."""

    enabled: bool = False
    http: str = ""
    https: str = ""
    no_proxy: str = Field(default="", alias="noProxy")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class GeneralResponse(BaseModel):
    """General settings response."""

    general: GeneralConfig

    model_config = ConfigDict(from_attributes=True)


class ProxyTestRequest(BaseModel):
    """Settings → Configuration → Test: the form's current values, saved or not."""

    url: str = Field(min_length=1, max_length=2048)
    proxy: ProxyConfig


class ConfigurationResponse(BaseModel):
    """Complete system configuration response."""

    proxy: ProxyConfig

    model_config = ConfigDict(from_attributes=True)


class TelegramBotConfigRequest(BaseModel):
    """Payload for PUT /settings/integrations/telegram."""

    bot_token: str | None = Field(None, alias="botToken")
    bot_username: str | None = Field(None, alias="botUsername")
    frontend_url: str | None = Field(None, alias="frontendUrl")

    model_config = ConfigDict(populate_by_name=True)


class SearchSettingsUpdate(BaseModel):
    """Payload for PUT /settings/search (slice 12): the embedding endpoint, and
    optionally the requested model and API key. ``None`` keeps the saved value,
    ``""`` clears it; ``api_key`` is write-only and never returned."""

    embedding_endpoint: str = Field(..., min_length=1, max_length=512)
    embedding_model: str | None = Field(None, max_length=128)
    api_key: str | None = Field(None, max_length=512)


class JevSettingsUpdate(BaseModel):
    """Payload for PUT /settings/search/jev (slice 13). Every field optional:
    ``api_key`` is write-only and never returned."""

    enabled: bool | None = None
    api_key: str | None = Field(None, max_length=512)
    model: str | None = Field(None, max_length=64)
