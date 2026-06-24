"""Environment-based settings (pydantic-settings).

`DEEPSEEK_API_KEY` is required — the app refuses to start without it.
Override defaults via environment variables or a `.env` file at the
project root (loaded automatically; see `.env.example`).
"""
from __future__ import annotations
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com/anthropic"
    deepseek_model: str = "deepseek-v4-flash"
    # Optional JSON string passed as the `thinking` parameter to the LLM.
    # Examples:
    #   DEEPSEEK_THINKING='{"type": "disabled"}'           # no internal thinking
    #   DEEPSEEK_THINKING='{"type": "enabled", "budget_tokens": 1024}'
    #   unset / empty                                       # model default
    deepseek_thinking: str = ""
    idea_max_length: int = 5000
    log_level: str = "INFO"
    request_timeout_s: int = 60


def get_settings() -> Settings:
    """Settings accessor (used as FastAPI dependency)."""
    return Settings()
