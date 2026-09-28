"""Helpers for gateway tests: committed users, keys, models, and settings in the test DB.

Gateway requests run in the app's own transactions, so fixtures commit their rows instead of
using the rolled-back `db` connection. Every name is unique per call to keep tests independent.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.gateway.keys import display_prefix, generate_key, hash_key
from app.ids import new_id
from tests.conftest import TEST_DATABASE_URL


@dataclass
class Member:
    user_id: uuid.UUID
    key: str
    api_key_id: uuid.UUID


class GatewayData:
    def __init__(self, engine: AsyncEngine) -> None:
        self.engine = engine

    async def user(
        self,
        *,
        balance: int = 100_000,
        tier: str = "basic",
        status: str = "active",
        daily_cap: int | None = None,
    ) -> uuid.UUID:
        user_id = new_id()
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO users (id, email, display_name, tier, status, balance_idr,"
                    " daily_cap_idr) VALUES (:id, :email, 'Test', :tier, :status, :balance, :cap)"
                ),
                {
                    "id": user_id,
                    "email": f"u-{user_id}@example.test",
                    "tier": tier,
                    "status": status,
                    "balance": balance,
                    "cap": daily_cap,
                },
            )
            if balance > 0:
                await conn.execute(
                    text(
                        "INSERT INTO ledger_entries (id, user_id, type, amount_idr,"
                        " balance_after_idr) VALUES (:id, :user_id, 'topup', :amount, :amount)"
                    ),
                    {"id": new_id(), "user_id": user_id, "amount": balance},
                )
        return user_id

    async def key(
        self,
        user_id: uuid.UUID,
        *,
        daily_cap: int | None = None,
        allowlist: list[str] | None = None,
    ) -> tuple[str, uuid.UUID]:
        key = generate_key()
        key_id = new_id()
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO api_keys (id, user_id, name, key_hash, key_prefix, daily_cap_idr,"
                    " model_allowlist) VALUES (:id, :user_id, 'test', :hash, :prefix, :cap, :allow)"
                ),
                {
                    "id": key_id,
                    "user_id": user_id,
                    "hash": hash_key(key),
                    "prefix": display_prefix(key),
                    "cap": daily_cap,
                    "allow": allowlist,
                },
            )
        return key, key_id

    async def member(self, **user_options: Any) -> Member:
        user_id = await self.user(**user_options)
        key, key_id = await self.key(user_id)
        return Member(user_id=user_id, key=key, api_key_id=key_id)

    async def model(
        self,
        scenario: str = "ok",
        *,
        api_format: str = "both",
        category: str = "official",
        min_tier: str = "basic",
        is_active: bool = True,
        prices: tuple[str, str, str, str] = ("0", "0", "0", "0"),
    ) -> str:
        """Create a catalog model backed by a fake-upstream scenario; returns its public name."""
        public_name = f"model-{uuid.uuid4().hex[:10]}"
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO models (id, public_name, upstream_id, api_format, provider,"
                    " category, min_tier, is_active, price_input_per_m, price_output_per_m,"
                    " price_cache_write_per_m, price_cache_read_per_m) VALUES (:id, :name,"
                    " :upstream, :fmt, 'fakeprovider', :cat, :tier, :active, :p0, :p1, :p2, :p3)"
                ),
                {
                    "id": new_id(),
                    "name": public_name,
                    "upstream": f"fake/{scenario}",
                    "fmt": api_format,
                    "cat": category,
                    "tier": min_tier,
                    "active": is_active,
                    "p0": Decimal(prices[0]),
                    "p1": Decimal(prices[1]),
                    "p2": Decimal(prices[2]),
                    "p3": Decimal(prices[3]),
                },
            )
        return public_name

    async def project(self, slug: str, official_only: bool) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO projects (id, slug, name, official_only) VALUES (:id, :slug,"
                    " :slug, :oo) ON CONFLICT (slug) DO UPDATE SET official_only = :oo"
                ),
                {"id": new_id(), "slug": slug, "oo": official_only},
            )

    async def fetch(self, sql: str, **params: Any) -> list[Any]:
        async with self.engine.connect() as conn:
            return list((await conn.execute(text(sql), params)).all())

    async def scalar(self, sql: str, **params: Any) -> Any:
        async with self.engine.connect() as conn:
            return await conn.scalar(text(sql), params)

    async def execute(self, sql: str, **params: Any) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(text(sql), params)


@asynccontextmanager
async def gateway_data() -> AsyncIterator[GatewayData]:
    engine = create_async_engine(TEST_DATABASE_URL)
    try:
        yield GatewayData(engine)
    finally:
        await engine.dispose()


@asynccontextmanager
async def setting(data: GatewayData, key: str, value: Any) -> AsyncIterator[None]:
    """Temporarily override a global setting row."""
    import json

    await data.execute(
        "INSERT INTO settings (id, key, value) VALUES (:id, :key, CAST(:value AS jsonb))"
        " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
        id=new_id(),
        key=key,
        value=json.dumps(value),
    )
    try:
        yield
    finally:
        await data.execute("DELETE FROM settings WHERE key = :key", key=key)


def openai_body(model: str, stream: bool = False, **extra: Any) -> dict[str, Any]:
    return {
        "model": model,
        "stream": stream,
        "messages": [{"role": "user", "content": "SECRET-PROMPT-TEXT tolong jawab singkat"}],
        **extra,
    }


def anthropic_body(model: str, stream: bool = False, **extra: Any) -> dict[str, Any]:
    return {
        "model": model,
        "stream": stream,
        "max_tokens": 64,
        "messages": [{"role": "user", "content": "SECRET-PROMPT-TEXT tolong jawab singkat"}],
        **extra,
    }


def auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}
