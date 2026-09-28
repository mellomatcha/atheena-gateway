"""Runtime settings stored in the `settings` table, with PRD defaults as fallback."""

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Setting

# Defaults from PRD §15 and the FR sections they refer to. `make seed` writes these rows;
# the gateway falls back to them when a row is missing.
DEFAULT_SETTINGS: dict[str, Any] = {
    "min_balance_idr": 1_000,  # FR-3.5, Q4
    "default_user_daily_cap_idr": None,  # FR-3.6, Q4: inactive
    "rate_limit_per_key_per_minute": 60,  # FR-3.7
    "rate_limit_per_user_per_minute": 120,  # FR-3.7: 2x per key, decided by owner
    "max_concurrent_streams_per_user": 8,  # FR-3.8
    "max_body_bytes": 20 * 1024 * 1024,  # FR-3.9: 20 MB
    "max_active_keys_per_user": 5,  # FR-2.5
    "default_low_balance_threshold_idr": 10_000,  # FR-5.5
}


@dataclass(frozen=True)
class GatewaySettings:
    min_balance_idr: int
    default_user_daily_cap_idr: int | None
    rate_limit_per_key_per_minute: int
    rate_limit_per_user_per_minute: int
    max_concurrent_streams_per_user: int
    max_body_bytes: int


async def load_settings(session: AsyncSession) -> dict[str, Any]:
    rows = (await session.execute(select(Setting.key, Setting.value))).all()
    return {**DEFAULT_SETTINGS, **{key: value for key, value in rows}}


async def load_gateway_settings(session: AsyncSession) -> GatewaySettings:
    values = await load_settings(session)
    cap = values["default_user_daily_cap_idr"]
    return GatewaySettings(
        min_balance_idr=int(values["min_balance_idr"]),
        default_user_daily_cap_idr=None if cap is None else int(cap),
        rate_limit_per_key_per_minute=int(values["rate_limit_per_key_per_minute"]),
        rate_limit_per_user_per_minute=int(values["rate_limit_per_user_per_minute"]),
        max_concurrent_streams_per_user=int(values["max_concurrent_streams_per_user"]),
        max_body_bytes=int(values["max_body_bytes"]),
    )
