"""Deployment configuration safety tests."""

import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_provider_postgres_urls_select_psycopg3_driver() -> None:
    settings = Settings(
        ENVIRONMENT="uat",
        DATABASE_URL="postgresql://app:secret@example.neon.tech/costing?sslmode=require",
        MIGRATION_DATABASE_URL="postgres://app:secret@example.neon.tech/costing?sslmode=require",
        SECRET_KEY="uat-secret-key-that-is-at-least-32-characters",
        CORS_ORIGINS=["https://drilling-costing.vercel.app"],
    )

    assert settings.DATABASE_URL.startswith("postgresql+psycopg://")
    assert settings.MIGRATION_DATABASE_URL is not None
    assert settings.MIGRATION_DATABASE_URL.startswith("postgresql+psycopg://")


def test_hosted_environment_rejects_development_secret() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY must be set for this environment"):
        Settings(
            ENVIRONMENT="uat",
            DATABASE_URL="postgresql://app:secret@example.neon.tech/costing",
            SECRET_KEY="development-only-change-me-please",
            CORS_ORIGINS=[],
        )


def test_hosted_environment_rejects_localhost_cors() -> None:
    with pytest.raises(ValidationError, match="localhost CORS"):
        Settings(
            ENVIRONMENT="uat",
            DATABASE_URL="postgresql://app:secret@example.neon.tech/costing",
            SECRET_KEY="uat-secret-key-that-is-at-least-32-characters",
            CORS_ORIGINS=["http://localhost:3000"],
        )
