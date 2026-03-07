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
    llm_model: str = "gpt-5-mini"
    llm_provider: str = "openai"
    llm_temperature: float = 0.7
    llm_base_url: Optional[str] = None

    # LLM API Keys (for various providers)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

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

    @property
    def sync_database_url(self) -> str:
        """Sync URL for Alembic migrations."""
        return self.database_url.replace("+asyncpg", "+psycopg2")


settings = Settings()
