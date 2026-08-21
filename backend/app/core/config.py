"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SECRET_KEY = "development-only-change-me-please"


def _normalize_postgres_url(value: str) -> str:
    """Select the installed Psycopg 3 driver for provider-issued PostgreSQL URLs."""

    if value.startswith("postgres://"):
        return value.replace("postgres://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


class Settings(BaseSettings):
    """Runtime configuration.

    Environment variables use the exact uppercase field names below. Local values may be
    stored in an uncommitted ``.env`` file copied from ``.env.example``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENVIRONMENT: Literal["development", "test", "termux", "uat", "staging", "production"] = (
        "development"
    )
    DATABASE_URL: str = "postgresql+psycopg://drilling_costing@localhost:5432/drilling_costing"
    MIGRATION_DATABASE_URL: str | None = None
    SECRET_KEY: str = Field(default=_DEFAULT_SECRET_KEY, min_length=32)
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    LOG_LEVEL: str = "INFO"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=1440)
    API_V1_PREFIX: str = "/api/v1"
    APP_VERSION: str = "0.1.0"
    # In development/termux environments the backend applies pending Alembic
    # migrations on startup so a pulled update can never leave the local
    # database behind the application schema. Hosted environments run
    # migrations in the build step instead. Set AUTO_MIGRATE=false to opt out.
    AUTO_MIGRATE: bool = True
    SUPABASE_URL: str | None = None
    SUPABASE_ANON_KEY: str | None = None
    SUPABASE_SERVICE_ROLE_KEY: str | None = None

    @field_validator("SUPABASE_URL", mode="before")
    @classmethod
    def normalize_supabase_url(cls, value: object) -> object:
        """Strip trailing slashes so token-endpoint joins stay clean."""

        return value.rstrip("/") if isinstance(value, str) and value else value

    @field_validator("DATABASE_URL", "MIGRATION_DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_urls(cls, value: object) -> object:
        """Normalize common managed-provider URLs without changing non-PostgreSQL tests."""

        return _normalize_postgres_url(value) if isinstance(value, str) else value

    @model_validator(mode="after")
    def reject_unsafe_hosted_configuration(self) -> Self:
        """Fail startup rather than silently using development defaults in hosted environments."""

        if self.ENVIRONMENT in {"termux", "uat", "staging", "production"}:
            if self.SECRET_KEY == _DEFAULT_SECRET_KEY or self.SECRET_KEY.startswith("replace-"):
                raise ValueError("SECRET_KEY must be set for this environment")
            if not self.DATABASE_URL.startswith("postgresql+psycopg://"):
                raise ValueError(
                    "termux/hosted environments require a PostgreSQL DATABASE_URL (use Supabase)"
                )
        if (
            self.ENVIRONMENT in {"uat", "staging", "production"}
            and any(origin.startswith("http://localhost") for origin in self.CORS_ORIGINS)
        ):
            raise ValueError("Hosted environments cannot allow localhost CORS origins")
        return self

    @property
    def supabase_auth_enabled(self) -> bool:
        """Whether Supabase Auth password sign-in is configured."""

        return bool(
            self.SUPABASE_URL and (self.SUPABASE_ANON_KEY or self.SUPABASE_SERVICE_ROLE_KEY)
        )

    @property
    def supabase_api_key(self) -> str:
        """API key used for Supabase Auth calls.

        The anon/public key is preferred for password sign-in (least privilege); the
        service-role key is used only when the anon key is absent.
        """

        key = self.SUPABASE_ANON_KEY or self.SUPABASE_SERVICE_ROLE_KEY
        return key if key is not None else ""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a process-wide cached settings instance."""

    return Settings()
