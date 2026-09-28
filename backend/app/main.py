from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis

from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker
from app.health import router as health_router
from app.logs import RequestContextMiddleware, configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Only connection pools live in process memory; all shared state is in Postgres/Redis.
        app.state.settings = settings
        app.state.engine = create_engine(settings.database_url)
        app.state.sessionmaker = create_sessionmaker(app.state.engine)
        app.state.redis = Redis.from_url(settings.redis_url)
        app.state.upstream = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        try:
            yield
        finally:
            await app.state.upstream.aclose()
            await app.state.redis.aclose()
            await app.state.engine.dispose()

    app = FastAPI(title="Atheena AI Gateway", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health_router)
    return app


app = create_app()
