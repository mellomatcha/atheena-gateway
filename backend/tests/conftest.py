import os
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import Settings
from app.main import create_app

# Tests never touch the development database or a real provider (CLAUDE.md).
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://agent@/atheena_test?host=/var/run/postgresql"
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
FAKE_UPSTREAM = "http://fake-upstream.test/v1"
FAKE_UPSTREAM_KEY = "fake-upstream-key"

BACKEND_DIR = Path(__file__).resolve().parents[1]


def alembic_config(database_url: str = TEST_DATABASE_URL) -> Config:
    config = Config(BACKEND_DIR / "alembic.ini")
    config.attributes["database_url"] = database_url
    config.attributes["configure_logger"] = False
    return config


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> Iterator[None]:
    """Rebuild the test schema from scratch once per session using the real migrations."""
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    yield


@pytest.fixture
async def db() -> AsyncIterator[AsyncConnection]:
    """A connection inside a transaction that is rolled back after the test."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.connect() as conn:
        transaction = await conn.begin()
        try:
            yield conn
        finally:
            await transaction.rollback()
    await engine.dispose()


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_env": "test",
        "database_url": TEST_DATABASE_URL,
        "redis_url": TEST_REDIS_URL,
        "upstream_base_url": FAKE_UPSTREAM,
        "upstream_api_key": SecretStr(FAKE_UPSTREAM_KEY),
        "seed_admin_email": "admin@example.test",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


ClientFactory = Callable[..., AbstractAsyncContextManager[httpx.AsyncClient]]


@pytest.fixture
def client_factory() -> ClientFactory:
    """Build an app with the given settings overrides and run its lifespan."""

    @asynccontextmanager
    async def factory(**overrides: object) -> AsyncIterator[httpx.AsyncClient]:
        app: FastAPI = create_app(make_settings(**overrides))
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                yield client

    return factory


@pytest.fixture(scope="session")
def fake_upstream_url() -> Iterator[str]:
    """Base URL (with /v1) of the fake upstream served on a real local port."""
    from tests.fake_upstream.app import app as fake_app
    from tests.fake_upstream.server import serve

    with serve(fake_app) as base:
        yield f"{base}/v1"


@pytest.fixture(scope="session", autouse=True)
def clean_test_redis() -> None:
    """Start every session with an empty test Redis database (rate limits, key cache)."""
    import redis as sync_redis

    sync_redis.Redis.from_url(TEST_REDIS_URL).flushdb()


# Short heartbeat timings so slow-TTFT scenarios run in well under a second each.
FAST_HEARTBEATS: dict[str, object] = {
    "stream_heartbeat_interval_s": 0.2,
    "nonstream_heartbeat_delay_s": 0.3,
    "nonstream_heartbeat_interval_s": 0.2,
}


@pytest.fixture
def gateway_factory(client_factory: ClientFactory, fake_upstream_url: str) -> ClientFactory:
    """Client factory for an app pointed at the fake upstream with fast heartbeats."""

    def factory(**overrides: object) -> AbstractAsyncContextManager[httpx.AsyncClient]:
        values = {"upstream_base_url": fake_upstream_url, **FAST_HEARTBEATS, **overrides}
        return client_factory(**values)

    return factory
