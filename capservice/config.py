from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_key: str = Field(..., min_length=8)
    public_base_url: str = Field(..., min_length=8)
    data_dir: Path = Path("./data")

    max_video_bytes: int = 100 * 1024 * 1024
    max_video_duration_seconds: float = 120
    download_timeout_seconds: float = 60
    processing_timeout_seconds: float = 600
    max_concurrent_jobs: int = 1
    output_retention_hours: float = 24
    stale_processing_seconds: float = 660
    max_process_attempts: int = 1
    worker_poll_seconds: float = 1.0

    webhook_max_attempts: int = 5
    webhook_timeout_seconds: float = 10
    webhook_backoff_base_seconds: float = 2

    default_template: str = "default"
    whisper_model: str = "base"
    whisper_backend: str = "faster"
    whisper_language: str | None = "es"

    @field_validator("public_base_url")
    @classmethod
    def strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("whisper_backend")
    @classmethod
    def validate_backend(cls, value: str) -> str:
        allowed = {"openai", "faster"}
        if value not in allowed:
            raise ValueError(f"whisper_backend must be one of {sorted(allowed)}")
        return value

    @property
    def db_path(self) -> Path:
        return self.data_dir / "capservice.db"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def outputs_dir(self) -> Path:
        return self.data_dir / "outputs"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)
    return settings


def reset_settings() -> None:
    get_settings.cache_clear()
