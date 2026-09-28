from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from redis.asyncio import Redis

from app.config import Settings, get_settings
from app.db import create_engine, create_sessionmaker
from app.gateway.routes import router as gateway_router
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
        app.state.upstream = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.upstream_connect_timeout_s,
                read=settings.upstream_read_timeout_s,
                write=30.0,
                pool=10.0,
            ),
            limits=httpx.Limits(max_connections=500, max_keepalive_connections=50),
        )
        try:
            yield
        finally:
            await app.state.upstream.aclose()
            await app.state.redis.aclose()
            await app.state.engine.dispose()

    app = FastAPI(title="Atheena AI Gateway", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health_router)
    app.include_router(gateway_router)
    return app


app = create_app()
