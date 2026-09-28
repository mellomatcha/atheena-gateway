"""System status for admins (FR-7.8, FR-7.9)."""

import time
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.gateway.limits import STREAM_SLOT_STALE_S
from app.health import CheckFailedError, check_upstream
from app.models import RequestLog
from app.portal.deps import AdminUser, SessionDep

router = APIRouter()

ROUTER_DASHBOARD_URL = "https://router.atheena.online"


class HealthOut(BaseModel):
    upstream_ok: bool
    upstream_error: str | None
    upstream_latency_ms: float | None
    active_streams: int
    requests_last_hour: int
    failed_last_hour: int
    upstream_failed_last_hour: int
    error_rate_last_hour: float
    avg_latency_ms_last_hour: float | None
    p95_latency_ms_last_hour: float | None
    router_dashboard_url: str


async def count_active_streams(request: Request) -> int:
    redis = request.app.state.redis
    cutoff = time.time() - STREAM_SLOT_STALE_S
    total = 0
    async for key in redis.scan_iter(match="streams:*", count=500):
        total += int(await redis.zcount(key, cutoff, "+inf"))
    return total


@router.get("/health")
async def health(request: Request, admin: AdminUser, session: SessionDep) -> HealthOut:
    state = request.app.state
    started = time.perf_counter()
    upstream_error: str | None = None
    try:
        await check_upstream(state.upstream, state.settings)
    except CheckFailedError as exc:
        upstream_error = str(exc)
    except Exception as exc:
        upstream_error = type(exc).__name__
    upstream_latency = round((time.perf_counter() - started) * 1000, 1)

    since = datetime.now(UTC) - timedelta(hours=1)
    row = (
        await session.execute(
            select(
                func.count().label("total"),
                func.count().filter(RequestLog.status_code >= 400).label("failed"),
                func.count()
                .filter(RequestLog.error_type.like("upstream%"))
                .label("upstream_failed"),
                func.avg(RequestLog.latency_ms)
                .filter(RequestLog.status_code < 400)
                .label("avg_latency"),
                func.percentile_cont(0.95)
                .within_group(RequestLog.latency_ms)
                .filter(RequestLog.status_code < 400)
                .label("p95_latency"),
            ).where(RequestLog.started_at >= since)
        )
    ).one()
    total = int(row.total)
    return HealthOut(
        upstream_ok=upstream_error is None,
        upstream_error=upstream_error,
        upstream_latency_ms=upstream_latency if upstream_error is None else None,
        active_streams=await count_active_streams(request),
        requests_last_hour=total,
        failed_last_hour=int(row.failed),
        upstream_failed_last_hour=int(row.upstream_failed),
        error_rate_last_hour=round(int(row.failed) / total, 4) if total else 0.0,
        avg_latency_ms_last_hour=None
        if row.avg_latency is None
        else round(float(row.avg_latency), 1),
        p95_latency_ms_last_hour=None
        if row.p95_latency is None
        else round(float(row.p95_latency), 1),
        router_dashboard_url=ROUTER_DASHBOARD_URL,
    )
