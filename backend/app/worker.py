"""Scheduled jobs (PRD §9.1 `worker`): daily usage rollup and monthly request partitions.

Run continuously with `python -m app.worker` (every 10 minutes) or once with `--once`.
A transaction-level advisory lock keeps two worker replicas from running a job at once.
"""

import argparse
import asyncio
import contextlib
import logging
import signal
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.config import get_settings
from app.gateway.billing import WIB
from app.ids import new_id
from app.logs import configure_logging
from app.models import RequestLog, UsageDaily
from app.services.usage import today_wib, wib_day

logger = logging.getLogger("atheena.worker")

INTERVAL_S = 600
# Arbitrary constant identifying this job in pg_advisory locks.
ROLLUP_LOCK_KEY = 417_001
PARTITION_MONTHS_AHEAD = 3


@dataclass(frozen=True)
class RollupResult:
    days: list[date]
    rows: int
    skipped: bool = False


async def rollup_days(conn: AsyncConnection, days: list[date]) -> int:
    """Recompute usage_daily for the given WIB days from requests (idempotent upsert)."""
    if not days:
        return 0
    day = wib_day().label("day")
    start = min(days)
    end = max(days) + timedelta(days=1)
    rows = (
        await conn.execute(
            select(
                day,
                RequestLog.user_id,
                RequestLog.model_id,
                RequestLog.project,
                func.sum(RequestLog.input_tokens).label("input_tokens"),
                func.sum(RequestLog.output_tokens).label("output_tokens"),
                func.sum(RequestLog.cache_write_tokens).label("cache_write_tokens"),
                func.sum(RequestLog.cache_read_tokens).label("cache_read_tokens"),
                func.sum(RequestLog.cost_idr).label("cost_idr"),
                func.count().label("request_count"),
            )
            .where(
                RequestLog.started_at >= datetime.combine(start, time(), WIB),
                RequestLog.started_at < datetime.combine(end, time(), WIB),
                RequestLog.user_id.is_not(None),
                RequestLog.model_id.is_not(None),
            )
            .group_by(day, RequestLog.user_id, RequestLog.model_id, RequestLog.project)
        )
    ).all()
    wanted = set(days)
    values = [
        {
            "id": new_id(),
            "day": row.day,
            "user_id": row.user_id,
            "model_id": row.model_id,
            "project": row.project,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "cache_write_tokens": row.cache_write_tokens,
            "cache_read_tokens": row.cache_read_tokens,
            "cost_idr": row.cost_idr,
            "request_count": row.request_count,
        }
        for row in rows
        if row.day in wanted
    ]
    if not values:
        return 0
    statement = insert(UsageDaily).values(values)
    await conn.execute(
        statement.on_conflict_do_update(
            index_elements=["day", "user_id", "model_id", "project"],
            set_={
                column: statement.excluded[column]
                for column in (
                    "input_tokens",
                    "output_tokens",
                    "cache_write_tokens",
                    "cache_read_tokens",
                    "cost_idr",
                    "request_count",
                )
            }
            | {"updated_at": func.now()},
        )
    )
    return len(values)


async def ensure_partitions(
    conn: AsyncConnection, months_ahead: int = PARTITION_MONTHS_AHEAD
) -> None:
    """Create monthly requests partitions ahead of time (closes the migration 0001 TODO).

    A partition cannot be created once requests_default holds rows in its range, so months
    are prepared well before they start.
    """
    for offset in range(months_ahead + 1):
        await conn.execute(
            text(
                "SELECT create_requests_partition("
                "(date_trunc('month', now()) + make_interval(months => :offset))::date)"
            ),
            {"offset": offset},
        )


async def run_once(engine: AsyncEngine, backfill_days: int = 1) -> RollupResult:
    today = today_wib()
    days = [today - timedelta(days=n) for n in range(backfill_days, -1, -1)]
    async with engine.begin() as conn:
        locked = await conn.scalar(
            text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": ROLLUP_LOCK_KEY}
        )
        if not locked:
            logger.info("rollup skipped: another worker holds the lock")
            return RollupResult(days=days, rows=0, skipped=True)
        await ensure_partitions(conn)
        rows = await rollup_days(conn, days)
    logger.info("rollup done", extra={"days": [d.isoformat() for d in days], "rows": rows})
    return RollupResult(days=days, rows=rows)


async def run_forever(engine: AsyncEngine, interval_s: int) -> None:
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    while not stop.is_set():
        try:
            await run_once(engine)
        except Exception as exc:
            logger.error("worker job failed", extra={"exc_type": type(exc).__name__})
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=interval_s)


async def _main(args: argparse.Namespace) -> int:
    engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    try:
        if args.once:
            await run_once(engine, backfill_days=args.backfill_days)
        else:
            await run_forever(engine, args.interval)
    finally:
        await engine.dispose()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.worker")
    parser.add_argument("--once", action="store_true", help="run the jobs once and exit")
    parser.add_argument(
        "--backfill-days", type=int, default=1, help="also recompute this many past days"
    )
    parser.add_argument("--interval", type=int, default=INTERVAL_S, help="seconds between runs")
    args = parser.parse_args(argv)
    configure_logging()
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())
