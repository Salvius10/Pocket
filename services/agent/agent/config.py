"""Agent settings. Only this service holds GEMINI_API_KEY; it is never sent to a phone."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", ".env"), extra="ignore")

    env: str = "local"
    core_api_url: str = "http://localhost:8080"
    internal_token: str = "local-internal-token"
    cors_origins: str = "*"

    gemini_mode: str = "fake"  # fake | live
    gemini_api_key: str = ""
    model_live: str = "gemini-3.8-live"
    model_flash: str = "gemini-3.8-flash"
    # Optional. Used only while MODEL_FLASH is unavailable (overloaded or timing out), and logged
    # every time. Empty = no model fallback: the composer drops to its rules instead.
    model_flash_fallback: str = ""
    live_voice_default: str = "Aoede"

    @property
    def is_live(self) -> bool:
        return self.gemini_mode == "live"


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.is_live and not s.gemini_api_key:
        raise RuntimeError("GEMINI_MODE=live needs GEMINI_API_KEY")
    return s
