from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, resolved from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_prefix="MARKETSCOPE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    sec_user_agent: str
    sec_requests_per_second: float = Field(default=8.0, gt=0, le=10.0)
    fred_api_key: str | None = None
    fred_requests_per_second: float = Field(default=5.0, gt=0)

    cache_dir: Path = Path("data/cache")
    cache_ttl_hours: int = Field(default=24, ge=0)
    request_timeout_seconds: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=4, ge=0)

    @field_validator("sec_user_agent")
    @classmethod
    def _require_contact_details(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError(
                "SEC requires a User-Agent containing contact details, "
                "for example 'MarketScope research aaron@example.com'"
            )
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
