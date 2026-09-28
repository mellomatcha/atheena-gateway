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

    # Proxy timing (FR-3.15). Overridable so tests can run slow-TTFT scenarios in seconds.
    upstream_connect_timeout_s: float = 10.0
    # Reasoning models can think for minutes before the first byte; heartbeats keep the client
    # connection alive meanwhile, so this only guards against a hung upstream.
    upstream_read_timeout_s: float = 600.0
    stream_heartbeat_interval_s: float = 15.0
    nonstream_heartbeat_delay_s: float = 30.0
    nonstream_heartbeat_interval_s: float = 15.0

    # Keyed hash for client IPs stored in requests.client_ip_hash; empty means a plain SHA-256.
    ip_hash_secret: SecretStr = SecretStr("")


@lru_cache
def get_settings() -> Settings:
    return Settings()
