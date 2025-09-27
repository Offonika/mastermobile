"""Application settings loaded from environment and .env files."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

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

    b24_base_url: str = Field(default="https://example.bitrix24.ru/rest", alias="B24_BASE_URL")
    b24_webhook_user_id: int = Field(default=1, alias="B24_WEBHOOK_USER_ID")
    b24_webhook_token: str = Field(default="changeme", alias="B24_WEBHOOK_TOKEN")
    b24_rate_limit_rps: float = Field(default=2.0, alias="B24_RATE_LIMIT_RPS")
    b24_backoff_seconds: int = Field(default=5, alias="B24_BACKOFF_SECONDS")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    whisper_rate_per_min_usd: float = Field(
        default=0.006,
        alias="WHISPER_RATE_PER_MIN_USD",
    )
    stt_max_file_minutes: int = Field(default=0, alias="STT_MAX_FILE_MINUTES")
    chatgpt_proxy_url: str | None = Field(default=None, alias="CHATGPT_PROXY_URL")

    storage_backend: Literal["local", "s3"] = Field(
        default="local",
        alias="STORAGE_BACKEND",
    )
    s3_endpoint_url: str | None = Field(default=None, alias="S3_ENDPOINT_URL")
    s3_region: str | None = Field(default=None, alias="S3_REGION")
    s3_bucket: str | None = Field(default=None, alias="S3_BUCKET")
    s3_access_key_id: str | None = Field(default=None, alias="S3_ACCESS_KEY_ID")
    s3_secret_access_key: str | None = Field(default=None, alias="S3_SECRET_ACCESS_KEY")
    local_storage_dir: str = Field(default="/app/storage", alias="LOCAL_STORAGE_DIR")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    jwt_secret: str = Field(default="changeme", alias="JWT_SECRET")
    jwt_issuer: str = Field(default="mastermobile", alias="JWT_ISSUER")
    cors_origins: str = Field(default="http://localhost:3000", alias="CORS_ORIGINS")
    max_page_size: int = Field(default=100, alias="MAX_PAGE_SIZE")
    request_timeout_s: int = Field(default=30, alias="REQUEST_TIMEOUT_S")
    enable_tracing: bool = Field(default=False, alias="ENABLE_TRACING")
    pii_masking_enabled: bool = Field(default=False, alias="PII_MASKING_ENABLED")
    disk_encryption_flag: bool = Field(default=False, alias="DISK_ENCRYPTION_FLAG")
    call_summary_enabled: bool = Field(default=False, alias="CALL_SUMMARY_ENABLED")

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
