"""Application settings loaded from environment and .env files."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application configuration."""

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.example"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="local", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    db_host: str = Field(default="db", alias="DB_HOST")
    db_port: int = Field(default=5432, alias="DB_PORT")
    db_user: str = Field(default="postgres", alias="DB_USER")
    db_password: str = Field(default="postgres", alias="DB_PASSWORD")
    db_name: str = Field(default="mastermobile", alias="DB_NAME")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    redis_host: str = Field(default="redis", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    chatgpt_proxy_url: str = Field(
        default="http://user150107:dx4a5m@102.129.178.65:6517",
        alias="CHATGPT_PROXY_URL",
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    jwt_secret: str = Field(default="changeme", alias="JWT_SECRET")
    jwt_issuer: str = Field(default="mastermobile", alias="JWT_ISSUER")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    max_page_size: int = Field(default=100, alias="MAX_PAGE_SIZE")
    request_timeout_s: int = Field(default=30, alias="REQUEST_TIMEOUT_S")
    enable_tracing: bool = Field(default=False, alias="ENABLE_TRACING")
    pii_masking_enabled: bool = Field(default=False, alias="PII_MASKING_ENABLED")
    disk_encryption_flag: bool = Field(default=False, alias="DISK_ENCRYPTION_FLAG")

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Return a SQLAlchemy-compatible database URL."""

        if self.database_url:
            return self.database_url

        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
