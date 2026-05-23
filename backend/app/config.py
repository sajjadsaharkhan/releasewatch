"""Application configuration via pydantic-settings.

All values can be supplied through environment variables or a .env file.
"""

from functools import lru_cache
from typing import List, Union

from pydantic import Field, field_validator, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings object — instantiated once at module level."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── General ───────────────────────────────────────────────────────────────
    SECRET_KEY: str = Field(..., description="Random secret used for signing JWTs")
    ENVIRONMENT: str = Field("development", description="development | staging | production")
    ALLOWED_ORIGINS: Union[str, List[str]] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
        description="CORS allowed origins (comma-separated string or JSON list)",
    )

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse ALLOWED_ORIGINS from string or list."""
        if isinstance(v, str):
            # Try to parse as JSON first
            import json
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                # Fall back to comma-separated
                return [origin.strip() for origin in v.split(",")]
        return v

    APP_VERSION: str = Field("0.1.0", description="Semantic version, injected by CI")

    # ── PostgreSQL ─────────────────────────────────────────────────────────────
    POSTGRES_HOST: str = Field("localhost", description="Database host")
    POSTGRES_PORT: int = Field(5432, description="Database port")
    POSTGRES_DB: str = Field("releasewatch", description="Database name")
    POSTGRES_USER: str = Field("releasewatch", description="Database user")
    POSTGRES_PASSWORD: str = Field("releasewatch", description="Database password")

    @computed_field  # type: ignore[misc]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy connection URL for asyncpg."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def sync_database_url(self) -> str:
        """Synchronous psycopg2 URL — used by Alembic offline mode if needed."""
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = Field("redis://localhost:6379/0", description="Redis connection URL")
    REDIS_CACHE_TTL: int = Field(300, description="Default cache TTL in seconds")

    # ── AWS S3 ────────────────────────────────────────────────────────────────
    S3_BUCKET_NAME: str = Field("releasewatch-attachments", description="S3 bucket for attachments")
    S3_ACCESS_KEY: str = Field("", description="AWS access key ID")
    S3_SECRET_KEY: str = Field("", description="AWS secret access key")
    S3_REGION: str = Field("us-east-1", description="AWS region")
    S3_PRESIGN_EXPIRY: int = Field(3600, description="Pre-signed URL expiry in seconds")

    # ── Telegram ──────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = Field("", description="Telegram bot token from @BotFather")
    TELEGRAM_BOT_USERNAME: str = Field("", description="Bot username without @")

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = Field("HS256", description="JWT signing algorithm")
    JWT_ACCESS_EXPIRE_MINUTES: int = Field(60, description="Access token lifetime in minutes")
    JWT_REFRESH_EXPIRE_DAYS: int = Field(30, description="Refresh token lifetime in days")


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance (singleton via lru_cache)."""
    return Settings()


# Module-level singleton — import this everywhere
settings: Settings = get_settings()
