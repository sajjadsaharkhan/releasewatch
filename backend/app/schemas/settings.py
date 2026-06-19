"""Settings schemas — for system configuration (proxy, LLM, etc.)."""

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


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    base_url: str = Field(default="", alias="baseUrl")
    api_key: str = Field(default="", alias="apiKey")
    embedding_model: str = Field(default="", alias="embeddingModel")

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


class GeneralResponse(BaseModel):
    """General settings response."""

    general: GeneralConfig

    model_config = ConfigDict(from_attributes=True)


class ConfigurationResponse(BaseModel):
    """Complete system configuration response."""

    proxy: ProxyConfig
    llm: LLMConfig

    model_config = ConfigDict(from_attributes=True)


class LLMTestRequest(BaseModel):
    """Request to test LLM connection."""

    base_url: str = Field(alias="baseUrl")
    api_key: str = Field(alias="apiKey")

    model_config = ConfigDict(
        populate_by_name=True,
    )


class LLMTestResponse(BaseModel):
    """Response from LLM connection test."""

    success: bool
    message: str


class TelegramBotConfigRequest(BaseModel):
    """Payload for PUT /settings/integrations/telegram."""

    bot_token: str | None = Field(None, alias="botToken")
    bot_username: str | None = Field(None, alias="botUsername")

    model_config = ConfigDict(populate_by_name=True)
