from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
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

    # Cloudflare Access (FR-1.2): team domain such as "atheena.cloudflareaccess.com" and the
    # Application Audience (AUD) tag of the portal application.
    cf_access_team_domain: str = ""
    cf_access_aud: str = ""
    # Top-up (FR-5.3): WhatsApp number for payment confirmations and the public path of the
    # static QRIS image. Both can change without rebuilding the frontend.
    topup_whatsapp_number: str = "6282312202002"
    topup_qris_path: str = "/assets/qris.png"

    # Development only: treat every dashboard request as this email. Refused in production.
    dev_auth_email: str | None = None

    @field_validator("app_env", mode="before")
    @classmethod
    def _env_aliases(cls, value: object) -> object:
        aliases = {"dev": "development", "prod": "production"}
        return aliases.get(value, value) if isinstance(value, str) else value

    @field_validator("dev_auth_email", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @model_validator(mode="after")
    def _production_requires_real_auth(self) -> "Settings":
        if self.app_env == "production":
            if self.dev_auth_email:
                raise ValueError("DEV_AUTH_EMAIL must not be set when APP_ENV=production")
            if not self.cf_access_team_domain or not self.cf_access_aud:
                raise ValueError(
                    "CF_ACCESS_TEAM_DOMAIN and CF_ACCESS_AUD are required when APP_ENV=production"
                )
        return self

    @property
    def dev_auth_bypass_email(self) -> str | None:
        """The bypass email, only ever returned in development."""
        if self.app_env == "development" and self.dev_auth_email:
            return self.dev_auth_email.strip().lower()
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
