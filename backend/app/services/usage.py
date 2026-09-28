"""Usage queries over the requests table (FR-6.1 to FR-6.4, FR-6.8; reused by admin in FR-7.3).

Days are Western Indonesia Time dates. Every query reads `requests` directly so that chart
totals always equal the sum of the request log for the same filters.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.billing import WIB
from app.models import ApiKey, RequestLog, User

MAX_RANGE_DAYS = 366
DEFAULT_RANGE_DAYS = 30
PAGE_SIZE = 50
EXPORT_ROW_LIMIT = 200_000
NO_PROJECT = "none"

Status = Literal["success", "failed"]


class UsageQueryError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class UsageFilter:
    """Filters shared by every usage view. user_id None means all users (admin only)."""

    start: date
    end: date  # inclusive
    user_id: uuid.UUID | None = None
    model: str | None = None
    api_key_id: uuid.UUID | None = None
    project: str | None = None
    status: Status | None = None

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.start, time(), WIB)

    @property
    def end_at(self) -> datetime:
        return datetime.combine(self.end + timedelta(days=1), time(), WIB)

    def conditions(self) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = [
            RequestLog.started_at >= self.start_at,
            RequestLog.started_at < self.end_at,
        ]
        if self.user_id is not None:
            conditions.append(RequestLog.user_id == self.user_id)
        if self.model:
            conditions.append(RequestLog.model_public_name == self.model)
        if self.api_key_id is not None:
            conditions.append(RequestLog.api_key_id == self.api_key_id)
        if self.project == NO_PROJECT:
            conditions.append(RequestLog.project.is_(None))
        elif self.project:
            conditions.append(RequestLog.project == self.project)
        if self.status == "success":
            conditions.append(RequestLog.status_code < 400)
        elif self.status == "failed":
            conditions.append(RequestLog.status_code >= 400)
        return conditions


def today_wib() -> date:
    return datetime.now(UTC).astimezone(WIB).date()


def make_filter(
    *,
    start: date | None,
    end: date | None,
    user_id: uuid.UUID | None,
    model: str | None = None,
    api_key_id: uuid.UUID | None = None,
    project: str | None = None,
    status: Status | None = None,
) -> UsageFilter:
    end = end or today_wib()
    start = start or end - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if start > end:
        raise UsageQueryError("Tanggal awal harus sebelum tanggal akhir.")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise UsageQueryError(f"Rentang tanggal maksimal {MAX_RANGE_DAYS} hari.")
    return UsageFilter(
        start=start,
        end=end,
        user_id=user_id,
        model=model or None,
        api_key_id=api_key_id,
        project=(project or "").strip().lower() or None,
        status=status,
    )


def wib_day() -> ColumnElement[date]:
    """The Western Indonesia Time calendar date of requests.started_at."""
    return func.date(func.timezone("Asia/Jakarta", RequestLog.started_at))


def _totals_columns() -> list[Any]:
    return [
        func.count().label("requests"),
        func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
        func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
        func.coalesce(func.sum(RequestLog.cache_write_tokens), 0).label("cache_write_tokens"),
        func.coalesce(func.sum(RequestLog.cache_read_tokens), 0).label("cache_read_tokens"),
        func.coalesce(func.sum(RequestLog.cost_idr), 0).label("cost_idr"),
    ]


@dataclass(frozen=True)
class Totals:
    requests: int
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    cost_idr: int

    @property
    def tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_write_tokens
            + self.cache_read_tokens
        )

    @classmethod
    def from_row(cls, row: Any) -> "Totals":
        return cls(
            requests=int(row.requests),
            input_tokens=int(row.input_tokens),
            output_tokens=int(row.output_tokens),
            cache_write_tokens=int(row.cache_write_tokens),
            cache_read_tokens=int(row.cache_read_tokens),
            cost_idr=int(row.cost_idr),
        )


async def totals(session: AsyncSession, flt: UsageFilter) -> Totals:
    row = (await session.execute(select(*_totals_columns()).where(*flt.conditions()))).one()
    return Totals.from_row(row)


async def top_model(session: AsyncSession, flt: UsageFilter) -> str | None:
    return await session.scalar(
        select(RequestLog.model_public_name)
        .where(*flt.conditions(), RequestLog.model_id.is_not(None))
        .group_by(RequestLog.model_public_name)
        .order_by(func.count().desc(), RequestLog.model_public_name)
        .limit(1)
    )


@dataclass(frozen=True)
class DayPoint:
    day: date
    totals: Totals


async def timeseries(session: AsyncSession, flt: UsageFilter) -> list[DayPoint]:
    day = wib_day().label("day")
    rows = (
        await session.execute(
            select(day, *_totals_columns()).where(*flt.conditions()).group_by(day).order_by(day)
        )
    ).all()
    by_day = {row.day: Totals.from_row(row) for row in rows}
    empty = Totals(0, 0, 0, 0, 0, 0)
    points = []
    current = flt.start
    while current <= flt.end:
        points.append(DayPoint(day=current, totals=by_day.get(current, empty)))
        current += timedelta(days=1)
    return points


def _log_query(flt: UsageFilter) -> Select[*tuple[Any, ...]]:
    return (
        select(
            RequestLog.request_id,
            RequestLog.started_at,
            RequestLog.model_public_name,
            RequestLog.project,
            RequestLog.endpoint,
            RequestLog.is_stream,
            RequestLog.status_code,
            RequestLog.error_type,
            RequestLog.input_tokens,
            RequestLog.output_tokens,
            RequestLog.cache_write_tokens,
            RequestLog.cache_read_tokens,
            RequestLog.usage_estimated,
            RequestLog.cost_idr,
            RequestLog.latency_ms,
            RequestLog.ttft_ms,
            RequestLog.api_key_id,
            ApiKey.name.label("key_name"),
            ApiKey.key_prefix.label("key_prefix"),
            RequestLog.user_id,
            User.display_name.label("user_name"),
            User.email.label("user_email"),
        )
        .outerjoin(ApiKey, ApiKey.id == RequestLog.api_key_id)
        .outerjoin(User, User.id == RequestLog.user_id)
        .where(*flt.conditions())
        .order_by(RequestLog.started_at.desc(), RequestLog.id.desc())
    )


async def request_page(session: AsyncSession, flt: UsageFilter, page: int) -> tuple[list[Any], int]:
    total = await session.scalar(select(func.count()).where(*flt.conditions()))
    rows = (
        await session.execute(_log_query(flt).limit(PAGE_SIZE).offset((page - 1) * PAGE_SIZE))
    ).all()
    return list(rows), int(total or 0)


async def stream_requests(session: AsyncSession, flt: UsageFilter) -> AsyncIterator[Any]:
    result = await session.stream(_log_query(flt).limit(EXPORT_ROW_LIMIT))
    async for row in result:
        yield row


async def facets(
    session: AsyncSession, user_id: uuid.UUID | None, since: date
) -> tuple[list[str], list[str]]:
    flt = UsageFilter(start=since, end=today_wib(), user_id=user_id)
    models = (
        await session.scalars(
            select(RequestLog.model_public_name)
            .where(*flt.conditions(), RequestLog.model_id.is_not(None))
            .group_by(RequestLog.model_public_name)
            .order_by(RequestLog.model_public_name)
        )
    ).all()
    projects = (
        await session.scalars(
            select(RequestLog.project)
            .where(*flt.conditions(), RequestLog.project.is_not(None))
            .group_by(RequestLog.project)
            .order_by(RequestLog.project)
        )
    ).all()
    return [m for m in models if m], [p for p in projects if p]
