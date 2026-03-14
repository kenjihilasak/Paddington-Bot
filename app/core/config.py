"""Environment-based application settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _to_sync_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if database_url.startswith("sqlite+aiosqlite:///"):
        return database_url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
    return database_url


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Paddington Bot Backend"
    app_env: str = "development"
    debug: bool = False
    api_prefix: str = "/api"
    business_timezone: str = "Europe/London"

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/paddington_bot"
    )
    redis_url: str = "redis://localhost:6379/0"

    meta_verify_token: str = "change-me"
    meta_access_token: str = ""
    meta_phone_number_id: str = ""
    meta_graph_version: str = "v21.0"

    llm_provider: str = "openai_compatible"
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: float = 15.0

    conversation_state_ttl_seconds: int = 86400
    default_offer_expiry_days: int = 30
    default_listing_expiry_days: int = 30
    default_summary_limit: int = 5
    webhook_log_payloads: bool = True

    @computed_field
    @property
    def sync_database_url(self) -> str:
        """Return a SQLAlchemy sync URL for Alembic."""

        return _to_sync_database_url(self.database_url)

    @property
    def is_meta_configured(self) -> bool:
        """Return whether Meta credentials are configured for outbound sending."""

        return bool(self.meta_access_token and self.meta_phone_number_id)

    @property
    def is_llm_configured(self) -> bool:
        """Return whether the configured LLM provider can be used."""

        return bool(self.llm_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings."""

    return Settings()

