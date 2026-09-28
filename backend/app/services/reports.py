"""Admin breakdowns and monthly reports read straight from requests (FR-7.3, FR-7.4)."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIModel, RequestLog, User
from app.services.usage import Totals, UsageFilter

Dimension = Literal["user", "model", "project", "provider"]


@dataclass(frozen=True)
class BreakdownRow:
    key: str | None
    label: str
    totals: Totals


def _totals_columns() -> list[Any]:
    return [
        func.count().label("requests"),
        func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(RequestLog.cache_write_tokens), 0).label("cache_write_tokens"),
        func.coalesce(func.sum(RequestLog.cache_read_tokens), 0).label("cache_read_tokens"),
        func.coalesce(func.sum(RequestLog.cost_idr), 0).label("cost_idr"),
    ]


async def breakdown(
    session: AsyncSession, flt: UsageFilter, dimension: Dimension, limit: int = 50
) -> list[BreakdownRow]:
    """Totals grouped by one dimension, most expensive first."""
    columns = _totals_columns()
    if dimension == "user":
        query = (
            select(
                RequestLog.user_id.label("key"),
                func.coalesce(User.display_name, "Tanpa user").label("label"),
                *columns,
            )
            .outerjoin(User, User.id == RequestLog.user_id)
            .group_by(RequestLog.user_id, User.display_name)
        )
    elif dimension == "model":
        query = select(
            RequestLog.model_public_name.label("key"),
            func.coalesce(RequestLog.model_public_name, "Tanpa model").label("label"),
            *columns,
        ).group_by(RequestLog.model_public_name)
    elif dimension == "project":
        query = select(
            RequestLog.project.label("key"),
            func.coalesce(RequestLog.project, "Tanpa proyek").label("label"),
            *columns,
        ).group_by(RequestLog.project)
    else:
        query = (
            select(
                AIModel.provider.label("key"),
                func.coalesce(AIModel.provider, "Tidak diketahui").label("label"),
                *columns,
            )
            .outerjoin(AIModel, AIModel.id == RequestLog.model_id)
            .group_by(AIModel.provider)
        )
    rows = (
        await session.execute(
            query.where(*flt.conditions())
            .order_by(func.sum(RequestLog.cost_idr).desc(), func.count().desc())
            .limit(limit)
        )
    ).all()
    return [
        BreakdownRow(
            key=None if row.key is None else str(row.key),
            label=row.label,
            totals=Totals.from_row(row),
        )
        for row in rows
    ]


def month_bounds(month: str) -> tuple[date, date]:
    """'2026-09' -> (2026-09-01, 2026-09-30), WIB calendar month."""
    year, mon = (int(part) for part in month.split("-"))
    start = date(year, mon, 1)
    next_month = date(year + (mon == 12), mon % 12 + 1, 1)
    return start, date.fromordinal(next_month.toordinal() - 1)


def month_filter(month: str) -> UsageFilter:
    start, end = month_bounds(month)
    return UsageFilter(start=start, end=end)


async def monthly_report(
    session: AsyncSession, month: str, by: Literal["project", "user"]
) -> list[BreakdownRow]:
    return await breakdown(session, month_filter(month), by, limit=10_000)
