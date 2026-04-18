from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    wokwi_cli_token: str = Field(default="", alias="WOKWI_CLI_TOKEN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    sonnet_model: str = "claude-sonnet-4-6"
    haiku_model: str = "claude-haiku-4-5-20251001"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
