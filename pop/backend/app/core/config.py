"""Application configuration and environment settings using Pydantic Settings."""

from functools import lru_cache
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """POP Backend global configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "ProofOfPresence (POP)"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field(default="development", description="Environment mode: development, staging, production, test")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # Security & JWT Tokens
    SECRET_KEY: str = Field(
        default="default_insecure_secret_key_change_in_production_894f28a9b31d4e78",
        description="Cryptographic secret key for signing JWT tokens",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["*"]

    # PostgreSQL Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://pop_user:pop_password@localhost:5432/pop_db",
        description="Async SQLAlchemy database connection URI",
    )
    DATABASE_SYNC_URL: str = Field(
        default="postgresql+psycopg2://pop_user:pop_password@localhost:5432/pop_db",
        description="Sync SQLAlchemy database connection URI for Alembic migrations",
    )

    # Redis Cache & Broker
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URI",
    )

    # Edge Ingestion Rules
    MAX_FUTURE_TIMESTAMP_SKEW_SECONDS: int = Field(
        default=300,
        description="Maximum tolerated future timestamp difference in seconds before rejecting edge readings",
    )
    DEFAULT_ROLLING_WINDOW_K: int = Field(
        default=5,
        description="Default rolling window size K for median filter on edge",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton instance."""
    return Settings()


settings = get_settings()
