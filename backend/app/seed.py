"""Idempotent development seed (`make seed`).

Existing rows are never overwritten, so values changed later by an admin survive a re-run.
"""

import asyncio
import sys
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import get_settings
from app.ids import new_id
from app.models import AIModel, Project, Setting, User

SEED_MEMBER_EMAIL = "member.contoh@example.com"

# Defaults from PRD §15 and the FR sections they refer to.
DEFAULT_SETTINGS: dict[str, Any] = {
    "min_balance_idr": 1_000,  # FR-3.5, Q4
    "default_user_daily_cap_idr": None,  # FR-3.6, Q4: inactive
    "rate_limit_per_key_per_minute": 60,  # FR-3.7
    "max_concurrent_streams_per_user": 8,  # FR-3.8
    "max_body_bytes": 20 * 1024 * 1024,  # FR-3.9: 20 MB
    "max_active_keys_per_user": 5,  # FR-2.5
    "default_low_balance_threshold_idr": 10_000,  # FR-5.5
}


@dataclass(frozen=True)
class SeedModel:
    public_name: str
    upstream_id: str
    api_format: str
    provider: str
    category: str
    min_tier: str
    context_window: int | None = None
    is_active: bool = True
    # Q1: every price starts at Rp 0; tokens are still recorded.
    price_input_per_m: Decimal = Decimal(0)
    price_output_per_m: Decimal = Decimal(0)
    price_cache_write_per_m: Decimal = Decimal(0)
    price_cache_read_per_m: Decimal = Decimal(0)


# Cheap starter catalog from 9Router. Public names carry no provider prefix (FR-4.0).
SEED_MODELS: tuple[SeedModel, ...] = ()


async def seed(conn: AsyncConnection, admin_email: str) -> None:
    users = [
        {
            "id": new_id(),
            "email": admin_email.strip().lower(),
            "display_name": "Admin",
            "role": "admin",
            "tier": "advanced",
            "status": "active",
        },
        {
            "id": new_id(),
            "email": SEED_MEMBER_EMAIL,
            "display_name": "Member Contoh",
            "role": "member",
            "tier": "basic",
            "status": "active",
        },
    ]
    await conn.execute(insert(User).values(users).on_conflict_do_nothing(index_elements=["email"]))

    await conn.execute(
        insert(Project)
        .values(id=new_id(), slug="helios", name="Helios", official_only=True)
        .on_conflict_do_nothing(index_elements=["slug"])
    )

    await conn.execute(
        insert(Setting)
        .values([{"id": new_id(), "key": k, "value": v} for k, v in DEFAULT_SETTINGS.items()])
        .on_conflict_do_nothing(index_elements=["key"])
    )

    if SEED_MODELS:
        await conn.execute(
            insert(AIModel)
            .values([{"id": new_id(), **asdict(model)} for model in SEED_MODELS])
            .on_conflict_do_nothing(index_elements=["public_name"])
        )


async def main() -> int:
    settings = get_settings()
    if not settings.seed_admin_email:
        print("SEED_ADMIN_EMAIL is not set; add it to .env", file=sys.stderr)
        return 1
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await seed(conn, settings.seed_admin_email)
    await engine.dispose()
    print(f"Seed complete: admin {settings.seed_admin_email}, {len(SEED_MODELS)} catalog models")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
