"""Liveness and readiness probes (PRD §8 Operasional, §12)."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter()

CHECK_TIMEOUT_S = 5.0


class CheckFailedError(Exception):
    """A readiness check failed with a reason that is safe to expose."""


async def check_postgres(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def check_redis(redis: Redis) -> None:
    await redis.ping()


async def check_upstream(client: httpx.AsyncClient, settings: Settings) -> None:
    api_key = settings.upstream_api_key.get_secret_value()
    if not api_key:
        raise CheckFailedError("UPSTREAM_API_KEY is not set")
    response = await client.get(
        f"{settings.upstream_base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    if response.status_code != 200:
        # Status code only; the upstream body is never echoed.
        raise CheckFailedError(f"upstream returned HTTP {response.status_code}")


async def _run_check(name: str, check: Callable[[], Awaitable[None]]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_S)
    except CheckFailedError as exc:
        error = str(exc)
    except TimeoutError:
        error = "timeout"
    except Exception as exc:
        # Exception type only; messages from drivers or upstream may carry payloads.
        error = type(exc).__name__
    else:
        return {"ok": True, "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
    logger.warning("readiness check failed", extra={"check": name, "error": error})
    return {"ok": False, "error": error}


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(request: Request) -> JSONResponse:
    state = request.app.state
    names = ("postgres", "redis", "upstream")
    results = await asyncio.gather(
        _run_check("postgres", lambda: check_postgres(state.engine)),
        _run_check("redis", lambda: check_redis(state.redis)),
        _run_check("upstream", lambda: check_upstream(state.upstream, state.settings)),
    )
    checks = dict(zip(names, results, strict=True))
    ready = all(result["ok"] for result in results)
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "ok" if ready else "fail", "checks": checks},
    )
