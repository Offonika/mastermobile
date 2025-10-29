"""Application settings loaded from environment and .env files."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
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

    worker_metrics_host: str = Field(default="0.0.0.0", alias="WORKER_METRICS_HOST")
    worker_metrics_port: int = Field(default=9100, alias="WORKER_METRICS_PORT")

    b24_base_url: str = Field(default="https://example.bitrix24.ru/rest", alias="B24_BASE_URL")
    b24_webhook_user_id: int = Field(default=1, alias="B24_WEBHOOK_USER_ID")
    b24_webhook_token: str = Field(default="changeme", alias="B24_WEBHOOK_TOKEN")
    b24_rate_limit_rps: float = Field(default=2.0, alias="B24_RATE_LIMIT_RPS")
    b24_backoff_seconds: int = Field(default=5, alias="B24_BACKOFF_SECONDS")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_project: str | None = Field(default=None, alias="OPENAI_PROJECT")
    openai_org: str | None = Field(default=None, alias="OPENAI_ORG")
    openai_workflow_id: str = Field(default="", alias="OPENAI_WORKFLOW_ID")
    openai_vector_store_id: str = Field(default="", alias="OPENAI_VECTOR_STORE_ID")
    whisper_rate_per_min_usd: float = Field(
        default=0.006,
        alias="WHISPER_RATE_PER_MIN_USD",
    )
    stt_default_engine: str = Field(default="stub", alias="STT_DEFAULT_ENGINE")
    stt_default_language: str | None = Field(default=None, alias="STT_DEFAULT_LANGUAGE")
    stt_openai_model: str = Field(default="whisper-1", alias="STT_OPENAI_MODEL")
    stt_openai_enabled: bool = Field(default=False, alias="STT_OPENAI_ENABLED")
    stt_local_enabled: bool = Field(default=False, alias="STT_LOCAL_ENABLED")
    stt_max_file_minutes: int = Field(default=0, alias="STT_MAX_FILE_MINUTES")
    stt_max_file_size_mb: int = Field(default=25, alias="STT_MAX_FILE_SIZE_MB", ge=0)
    stt_error_hint_413: str = Field(
        default="Файл превышает допустимые ограничения.",
        alias="STT_ERROR_HINT_413",
    )
    stt_error_hint_422: str = Field(
        default="Формат записи не распознан. Попробуйте WAV/MP3/M4A.",
        alias="STT_ERROR_HINT_422",
    )
    local_stt_url: str | None = Field(default=None, alias="LOCAL_STT_URL")
    local_stt_api_key: str | None = Field(default=None, alias="LOCAL_STT_API_KEY")
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
    raw_recording_retention_days: int = Field(
        default=90,
        alias="RAW_RECORDING_RETENTION_DAYS",
        ge=0,
    )
    transcript_retention_days: int = Field(
        default=180,
        alias="TRANSCRIPT_RETENTION_DAYS",
        ge=0,
    )
    summary_retention_days: int = Field(
        default=365,
        alias="SUMMARY_RETENTION_DAYS",
        ge=0,
    )
    storage_cleanup_interval_hours: float = Field(
        default=24.0,
        alias="STORAGE_CLEANUP_INTERVAL_HOURS",
        ge=0.0,
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
    call_summary_enabled: bool = Field(default=False, alias="CALL_SUMMARY_ENABLED")

    # --- Shim для обратной совместимости со старым кодом ---
    @property
    def OPENAI_API_KEY(self) -> str | None:
        return self.openai_api_key

    @property
    def OPENAI_WORKFLOW_ID(self) -> str | None:
        return self.openai_workflow_id

    @property
    def CORS_ORIGINS(self) -> str | None:
        return self.cors_origins

    @model_validator(mode="before")
    @classmethod
    def enable_pii_masking_by_default(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Turn on PII masking by default for non-local environments."""

        if isinstance(data, dict) and not any(
            key in data for key in ("PII_MASKING_ENABLED", "pii_masking_enabled")
        ):
            app_env = data.get("APP_ENV", data.get("app_env", "local"))
            if isinstance(app_env, str) and app_env != "local":
                data["pii_masking_enabled"] = True
        return data

    @model_validator(mode="after")
    def validate_openai_workflow_configuration(self) -> "Settings":
        """Ensure workflow integration has all required settings configured."""

        workflow_id = (self.openai_workflow_id or "").strip()
        if not workflow_id:
            return self

        missing: list[str] = []
        if not (self.openai_api_key or "").strip():
            missing.append("OPENAI_API_KEY")
        if not (self.openai_project or "").strip():
            missing.append("OPENAI_PROJECT")
        if not (self.openai_base_url or "").strip():
            missing.append("OPENAI_BASE_URL")

        if missing:
            joined = ", ".join(sorted(missing))
            raise ValueError(
                "OPENAI_WORKFLOW_ID requires the following settings to be provided: "
                f"{joined}."
            )

        return self

    @property
    def sqlalchemy_database_uri(self) -> str:
        """Return a SQLAlchemy-compatible database URL."""

        if self.database_url:
            return self.database_url

        return (
            f"postgresql+psycopg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def cors_allowed_origins(self) -> list[str]:
        """Return a list of allowed CORS origins including required domains."""

        origins: list[str] = []
        for origin in self.cors_origins.split(","):
            normalized = origin.strip()
            if normalized and normalized not in origins:
                origins.append(normalized)

        extras: set[str] = {"https://master-mobile.ru"}

        parsed_b24 = urlsplit(self.b24_base_url)
        if parsed_b24.scheme and parsed_b24.netloc:
            extras.add(f"{parsed_b24.scheme}://{parsed_b24.netloc}")

        for extra in extras:
            if extra and extra not in origins:
                origins.append(extra)

        return origins


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
