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

    # ── AWS S3 / MinIO ─────────────────────────────────────────────────────────
    S3_ENDPOINT_URL: str = Field("", description="Custom S3 endpoint (e.g., MinIO)")
    S3_BUCKET_NAME: str = Field("releasewatch-attachments", description="S3 bucket for attachments")
    S3_ACCESS_KEY: str = Field("", description="AWS access key ID")
    S3_SECRET_KEY: str = Field("", description="AWS secret access key")
    S3_REGION: str = Field("us-east-1", description="AWS region")
    S3_PRESIGN_EXPIRY: int = Field(3600, description="Pre-signed URL expiry in seconds")
    S3_USE_PRESIGNED: bool = Field(True, description="Use presigned URLs; if False, generates public URLs")
    S3_LARGE_FILE_THRESHOLD_MB: int = Field(100, description="File size threshold (MB) for lifecycle retention")
    S3_LARGE_FILE_RETENTION_DAYS: int = Field(60, description="Days before auto-deletion of large files")
    S3_PUBLIC_URL_BASE: str = Field("", description="Base URL for public S3 access (e.g., CDN)")

    # ── Frontend ──────────────────────────────────────────────────────────────
    FRONTEND_URL: str = Field("http://localhost:5173", description="Public base URL of the frontend app (used in Telegram links)")

    # ── Telegram ──────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = Field("", description="Telegram bot token from @BotFather")
    TELEGRAM_BOT_USERNAME: str = Field("", description="Bot username without @")

    # ── Admin bootstrap ───────────────────────────────────────────────────────
    ADMIN_PASSWORD: str = Field("", description="Initial password for the built-in admin account (username: admin)")

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_ALGORITHM: str = Field("HS256", description="JWT signing algorithm")
    JWT_ACCESS_EXPIRE_MINUTES: int = Field(60, description="Access token lifetime in minutes")
    JWT_REFRESH_EXPIRE_DAYS: int = Field(30, description="Refresh token lifetime in days")

    # ── Federated auth (optional) ───────────────────────────────────────────────
    # External identity providers are OPTIONAL and ADDITIVE. Each is enabled only
    # when its required settings are present; with none set, Releasewatch runs
    # exactly as before with local username/password accounts.
    FEDERATED_DEFAULT_ROLE: str = Field(
        "developer",
        description="Role seeded for users JIT-provisioned via a provider (Phase 1)",
    )

    # Keycloak (OIDC) — enabled when issuer + client id + client secret are set
    KEYCLOAK_ISSUER: str = Field(
        "", description="Realm base URL, e.g. https://kc.example.com/realms/rw"
    )
    KEYCLOAK_CLIENT_ID: str = Field("", description="Confidential client id")
    KEYCLOAK_CLIENT_SECRET: str = Field("", description="Confidential client secret")
    KEYCLOAK_REDIRECT_URI: str = Field(
        "", description="RW backend callback URL; must be whitelisted in the Keycloak client"
    )
    KEYCLOAK_SCOPES: str = Field("openid profile email", description="OIDC scopes requested")

    # LDAP / Active Directory — enabled when server URI + a bind template/base set
    LDAP_SERVER_URI: str = Field("", description="e.g. ldaps://ad.corp.local:636")
    LDAP_BIND_DN_TEMPLATE: str = Field(
        "", description="Direct bind template, e.g. {username}@corp.local (AD UPN)"
    )
    LDAP_USER_BASE_DN: str = Field(
        "", description="Search base for search-then-bind, e.g. OU=Users,DC=corp,DC=local"
    )
    LDAP_USER_FILTER: str = Field(
        "(userPrincipalName={username})", description="User search filter for search-then-bind"
    )
    LDAP_SERVICE_BIND_DN: str = Field(
        "", description="Service account DN (only for search-then-bind)"
    )
    LDAP_SERVICE_PASSWORD: str = Field("", description="Service account password")
    LDAP_USE_TLS: bool = Field(True, description="Require TLS/LDAPS for binds")
    LDAP_ATTR_NAME: str = Field("displayName", description="AD attribute for the display name")
    LDAP_ATTR_EMAIL: str = Field("mail", description="AD attribute for the email address")

    @computed_field  # type: ignore[misc]
    @property
    def keycloak_enabled(self) -> bool:
        """True when Keycloak OIDC login is fully configured."""
        return bool(
            self.KEYCLOAK_ISSUER
            and self.KEYCLOAK_CLIENT_ID
            and self.KEYCLOAK_CLIENT_SECRET
            and self.KEYCLOAK_REDIRECT_URI
        )

    @computed_field  # type: ignore[misc]
    @property
    def ldap_enabled(self) -> bool:
        """True when direct LDAP/AD bind is configured (direct-bind or search-then-bind)."""
        return bool(
            self.LDAP_SERVER_URI
            and (self.LDAP_BIND_DN_TEMPLATE or (self.LDAP_SERVICE_BIND_DN and self.LDAP_USER_BASE_DN))
        )


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance (singleton via lru_cache)."""
    return Settings()


# Module-level singleton — import this everywhere
settings: Settings = get_settings()
