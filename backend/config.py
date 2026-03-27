"""
Centralized configuration using pydantic-settings.
Loads from environment variables and .env file.
"""

from typing import Optional
from pydantic import model_validator
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
    llm_model: str = "gpt-5-mini"
    llm_provider: str = "openai"
    llm_temperature: float = 0.7
    llm_base_url: Optional[str] = None

    # LLM API Keys (for various providers)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # Langfuse tracing
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_tracing_environment: str = "development"

    # Encryption key for sensitive settings (generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    settings_encryption_key: str = "sentinel-encryption-key-change-in-production"

    # PPIP / e-GP
    ppip_base_url: str = "https://tenders.go.ke/api/ocds"
    ppip_timeout: float = 30.0

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # JWT Authentication
    jwt_secret_key: str = "sentinel-dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # Neo4j Graph Database
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "sentinel123"
    neo4j_database: str = "neo4j"
    neo4j_enabled: bool = True  # Set to False to use NetworkX fallback

    @model_validator(mode="after")
    def fix_database_url(self) -> "Settings":
        """Normalize DATABASE_URL for asyncpg compatibility.

        Handles:
        - Railway/Neon: postgres:// or postgresql:// → postgresql+asyncpg://
        - Neon SSL: ?sslmode=require → ?ssl=require (asyncpg uses ssl= not sslmode=)
        """
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = url.replace("sslmode=require", "ssl=require")
        self.database_url = url
        return self

    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic migrations (psycopg2 driver, sslmode= not ssl=)."""
        return self.database_url.replace("+asyncpg", "+psycopg2").replace(
            "ssl=require", "sslmode=require"
        )


settings = Settings()
