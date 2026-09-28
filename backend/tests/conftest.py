import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app

# Tests never touch the development database or a real provider (CLAUDE.md).
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://agent@/atheena_test?host=/var/run/postgresql"
)
TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")
FAKE_UPSTREAM = "http://fake-upstream.test/v1"
FAKE_UPSTREAM_KEY = "fake-upstream-key"


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
