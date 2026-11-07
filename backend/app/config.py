"""Application settings, read from environment variables (or a local .env file)."""
import logging
import secrets
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("shotsense")

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database: SQLite for local development, PostgreSQL in production.
    database_url: str = f"sqlite:///{BACKEND_DIR / 'shotsense.db'}"

    # Auth
    secret_key: str = ""
    access_token_expire_minutes: int = 60 * 24 * 7

    # Comma-separated list of allowed frontend origins.
    cors_origins: str = "http://localhost:5173"

    # Model artifacts produced by training/train_shotsense.ipynb
    model_dir: Path = BACKEND_DIR / "model"

    # Upload limits
    max_upload_mb: int = 200
    max_video_seconds: int = 600
    max_shots: int = 60

    # LLM layer. Provider "auto" picks Anthropic, then OpenAI, based on which key is set.
    llm_provider: str = "auto"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-5-5"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    llm_vision: bool = True
    llm_max_shots: int = 24
    llm_timeout_seconds: float = 60.0

    # One-time demo: "Try the demo" creates a private guest account with a small quota.
    # A browser cookie and the visitor's (hashed) IP address stop the same person
    # starting a second demo within guest_ip_window_hours.
    guest_enabled: bool = True
    guest_max_analyses: int = 3
    guest_session_hours: int = 24
    guest_ip_window_hours: int = 24 * 30
    guest_per_ip: int = 1

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        url = self.database_url
        # Render/Heroku/Neon hand out postgres:// URLs; SQLAlchemy needs a driver name.
        if url.startswith("postgres://"):
            url = "postgresql+psycopg://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if not settings.secret_key:
        settings.secret_key = secrets.token_urlsafe(48)
        log.warning("SECRET_KEY is not set: using a random key, so logins reset on restart.")
    return settings
