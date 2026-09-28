"""Internal leaderboard from the daily rollup (FR-8.1 to FR-8.4).

Reads usage_daily, so figures trail live usage by at most one worker interval (10 minutes).
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

from sqlalchemy import ColumnElement, Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UsageDaily, User
from app.services.usage import today_wib

Period = Literal["week", "month"]
Metric = Literal["tokens", "requests", "cost", "efficiency"]

# FR-8.2: efficiency is only fair with enough requests behind it.
EFFICIENCY_MIN_REQUESTS = 100
LIMIT = 50


@dataclass(frozen=True)
class Entry:
    rank: int
    user_id: uuid.UUID
    display_name: str
    value: float
    requests: int


def period_bounds(period: Period, today: date | None = None) -> tuple[date, date]:
    """Current week (Monday to today) or calendar month (1st to today), WIB dates."""
    today = today or today_wib()
    if period == "week":
        return today - timedelta(days=today.weekday()), today
    return today.replace(day=1), today


async def leaderboard(
    session: AsyncSession, period: Period, metric: Metric, today: date | None = None
) -> tuple[date, date, list[Entry]]:
    start, end = period_bounds(period, today)
    requests = func.sum(UsageDaily.request_count)
    tokens = func.sum(
        UsageDaily.input_tokens
        + UsageDaily.output_tokens
        + UsageDaily.cache_write_tokens
        + UsageDaily.cache_read_tokens
    )
    total_input = func.sum(
        UsageDaily.input_tokens + UsageDaily.cache_write_tokens + UsageDaily.cache_read_tokens
    )
    efficiency = cast(func.sum(UsageDaily.cache_read_tokens), Float) / func.nullif(total_input, 0)
    metrics: dict[str, ColumnElement[Any]] = {
        "tokens": tokens,
        "requests": requests,
        "cost": func.sum(UsageDaily.cost_idr),
        "efficiency": func.coalesce(efficiency, 0.0),
    }
    value = metrics[metric].label("value")

    query = (
        select(UsageDaily.user_id, User.display_name, value, requests.label("requests"))
        .join(User, User.id == UsageDaily.user_id)
        .where(
            UsageDaily.day >= start,
            UsageDaily.day <= end,
            User.status == "active",
            User.leaderboard_opt_out.is_(False),  # FR-8.4
        )
        .group_by(UsageDaily.user_id, User.display_name)
        .order_by(value.desc(), User.display_name)
        .limit(LIMIT)
    )
    if metric == "efficiency":
        query = query.having(requests >= EFFICIENCY_MIN_REQUESTS)
    rows = (await session.execute(query)).all()
    entries = [
        Entry(
            rank=index + 1,
            user_id=row.user_id,
            display_name=row.display_name,
            value=float(row.value or 0),
            requests=int(row.requests),
        )
        for index, row in enumerate(rows)
    ]
    return start, end, entries
