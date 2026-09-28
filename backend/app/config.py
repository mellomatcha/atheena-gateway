from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# The .env file lives at the repository root, next to .env.example.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://agent@/atheena?host=/var/run/postgresql"
    redis_url: str = "redis://127.0.0.1:6379/0"
    upstream_base_url: str = "http://10.10.10.13:3000/v1"
    upstream_api_key: SecretStr = SecretStr("")
    seed_admin_email: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
