"""
Centralized configuration using pydantic-settings.
Loads from environment variables and .env file.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://sentinel:sentinel@localhost:5432/sentinel"
    db_echo: bool = False
    db_pool_size: int = 10
    db_max_overflow: int = 20

    # LLM
    llm_model: str = "gpt-4o-mini"
    llm_provider: str = "openai"
    llm_temperature: float = 0
    llm_base_url: Optional[str] = None

    # PPIP / e-GP
    ppip_base_url: str = "https://tenders.go.ke/api/ocds"
    ppip_timeout: float = 30.0

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "+psycopg2")


settings = Settings()
