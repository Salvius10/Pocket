"""Settings. Everything comes from the environment (.env locally, Cloud Run env vars in demo)."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings, SettingsConfigDict

IST = ZoneInfo("Asia/Kolkata")
REPO_ROOT = Path(__file__).resolve().parents[3]


def _find_data_dir() -> Path:
    for base in (Path.cwd(), REPO_ROOT, Path("/app")):
        if (base / "data" / "reference" / "categories.csv").exists():
            return base / "data"
    return REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(REPO_ROOT / ".env", ".env"), extra="ignore")

    env: str = "local"
    auth_mode: str = "dev"  # dev | firebase
    firebase_project_id: str = ""
    database_url: str = ""
    test_database_url: str = ""
    internal_token: str = "local-internal-token"
    agent_url: str = "http://localhost:8081"
    pocket_today: str = ""
    data_dir: str = ""
    cors_origins: str = "*"
    gold_price_per_gram_paise: int = 0
    nifty_proxy_scheme_code: int = 120716  # UTI Nifty 50 Index Fund - Direct Growth

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        local = REPO_ROOT / ".local"
        local.mkdir(exist_ok=True)
        return f"sqlite+aiosqlite:///{(local / 'pocket.db').as_posix()}"

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir) if self.data_dir else _find_data_dir()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def today_ist() -> date:
    """Today's IST date. POCKET_TODAY freezes it so a demo stays aligned with the dataset."""
    s = get_settings().pocket_today
    if s:
        return date.fromisoformat(s)
    return datetime.now(IST).date()


def now_utc() -> datetime:
    from datetime import UTC

    return datetime.now(UTC)
