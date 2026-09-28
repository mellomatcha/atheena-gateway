"""Member usage views (§8: /usage/summary, /timeseries, /requests, /export.csv; FR-6.1 to 6.8)."""

import csv
import io
import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import Settings
from app.portal.deps import CurrentUser, PortalError, SessionDep
from app.services import usage
from app.services.usage import Status, Totals, UsageFilter, UsageQueryError

router = APIRouter()


class TotalsOut(BaseModel):
    requests: int
    tokens: int
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    cost_idr: int

    @classmethod
    def of(cls, t: Totals) -> "TotalsOut":
        return cls(
            requests=t.requests,
            tokens=t.tokens,
            input_tokens=t.input_tokens,
            output_tokens=t.output_tokens,
            cache_write_tokens=t.cache_write_tokens,
            cache_read_tokens=t.cache_read_tokens,
            cost_idr=t.cost_idr,
        )


class FilterParams:
    """Query parameters shared by every usage endpoint."""

    def __init__(
        self,
        start: Annotated[date | None, Query(alias="from")] = None,
        end: Annotated[date | None, Query(alias="to")] = None,
        model: Annotated[str | None, Query(max_length=200)] = None,
        key: uuid.UUID | None = None,
        project: Annotated[str | None, Query(max_length=64)] = None,
        status: Status | None = None,
    ) -> None:
        self.start = start
        self.end = end
        self.model = model
        self.key = key
        self.project = project
        self.status = status

    def build(self, user_id: uuid.UUID | None) -> UsageFilter:
        try:
            return usage.make_filter(
                start=self.start,
                end=self.end,
                user_id=user_id,
                model=self.model,
                api_key_id=self.key,
                project=self.project,
                status=self.status,
            )
        except UsageQueryError as exc:
            raise PortalError(400, "invalid_range", exc.message) from exc


Filters = Annotated[FilterParams, Depends()]


class SummaryOut(BaseModel):
    balance_idr: int
    today: TotalsOut
    last_7_days: TotalsOut
    last_30_days: TotalsOut
    top_model_30_days: str | None


@router.get("/usage/summary")
async def summary(user: CurrentUser, session: SessionDep) -> SummaryOut:
    today = usage.today_wib()

    def window(days: int) -> UsageFilter:
        return UsageFilter(start=today - timedelta(days=days - 1), end=today, user_id=user.id)

    return SummaryOut(
        balance_idr=user.balance_idr,
        today=TotalsOut.of(await usage.totals(session, window(1))),
        last_7_days=TotalsOut.of(await usage.totals(session, window(7))),
        last_30_days=TotalsOut.of(await usage.totals(session, window(30))),
        top_model_30_days=await usage.top_model(session, window(30)),
    )


class DayOut(BaseModel):
    day: date
    value: int
    totals: TotalsOut


class TimeseriesOut(BaseModel):
    unit: Literal["token", "idr"]
    start: date
    end: date
    points: list[DayOut]
    range_totals: TotalsOut


async def build_timeseries(
    session: Any, flt: UsageFilter, unit: Literal["token", "idr"]
) -> TimeseriesOut:
    points = await usage.timeseries(session, flt)
    return TimeseriesOut(
        unit=unit,
        start=flt.start,
        end=flt.end,
        points=[
            DayOut(
                day=p.day,
                value=p.totals.cost_idr if unit == "idr" else p.totals.tokens,
                totals=TotalsOut.of(p.totals),
            )
            for p in points
        ],
        range_totals=TotalsOut.of(await usage.totals(session, flt)),
    )


@router.get("/usage/timeseries")
async def get_timeseries(
    user: CurrentUser,
    session: SessionDep,
    filters: Filters,
    unit: Literal["token", "idr"] = "idr",
) -> TimeseriesOut:
    return await build_timeseries(session, filters.build(user.id), unit)


class RequestRow(BaseModel):
    request_id: uuid.UUID
    started_at: datetime
    model: str | None
    project: str | None
    endpoint: str
    stream: bool
    status_code: int
    error_type: str | None
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    usage_estimated: bool
    cost_idr: int
    latency_ms: int | None
    ttft_ms: int | None
    key_id: uuid.UUID | None
    key_name: str | None
    key_prefix: str | None
    user_id: uuid.UUID | None = None
    user_name: str | None = None

    @classmethod
    def of(cls, row: Any, include_user: bool = False) -> "RequestRow":
        return cls(
            request_id=row.request_id,
            started_at=row.started_at,
            model=row.model_public_name,
            project=row.project,
            endpoint=row.endpoint,
            stream=row.is_stream,
            status_code=row.status_code,
            error_type=row.error_type,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cache_write_tokens=row.cache_write_tokens,
            cache_read_tokens=row.cache_read_tokens,
            usage_estimated=row.usage_estimated,
            cost_idr=row.cost_idr,
            latency_ms=row.latency_ms,
            ttft_ms=row.ttft_ms,
            key_id=row.api_key_id,
            key_name=row.key_name,
            key_prefix=row.key_prefix,
            user_id=row.user_id if include_user else None,
            user_name=row.user_name if include_user else None,
        )


class RequestPage(BaseModel):
    items: list[RequestRow]
    page: int
    page_size: int
    total: int


async def build_request_page(
    session: Any, flt: UsageFilter, page: int, include_user: bool = False
) -> RequestPage:
    rows, total = await usage.request_page(session, flt, page)
    return RequestPage(
        items=[RequestRow.of(r, include_user) for r in rows],
        page=page,
        page_size=usage.PAGE_SIZE,
        total=total,
    )


@router.get("/usage/requests")
async def get_requests(
    user: CurrentUser,
    session: SessionDep,
    filters: Filters,
    page: int = Query(1, ge=1, le=100_000),
) -> RequestPage:
    return await build_request_page(session, filters.build(user.id), page)


_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

CSV_COLUMNS = [
    "waktu_wib",
    "request_id",
    "model",
    "proyek",
    "key",
    "endpoint",
    "stream",
    "status",
    "error",
    "input_tokens",
    "output_tokens",
    "cache_write_tokens",
    "cache_read_tokens",
    "estimasi",
    "biaya_idr",
    "latency_ms",
    "ttft_ms",
]


def csv_safe(value: object) -> str:
    """Neutralize spreadsheet formulas in text cells (CSV injection). Numbers pass through."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "ya" if value else "tidak"
    if isinstance(value, int):
        return str(value)
    text = str(value)
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


def csv_row(row: Any, include_user: bool = False) -> list[str]:
    from app.gateway.billing import WIB

    values: list[object] = [
        row.started_at.astimezone(WIB).strftime("%Y-%m-%d %H:%M:%S"),
        str(row.request_id),
        row.model_public_name,
        row.project,
        f"{row.key_name} ({row.key_prefix})" if row.key_name else None,
        row.endpoint,
        row.is_stream,
        row.status_code,
        row.error_type,
        row.input_tokens,
        row.output_tokens,
        row.cache_write_tokens,
        row.cache_read_tokens,
        row.usage_estimated,
        row.cost_idr,
        row.latency_ms,
        row.ttft_ms,
    ]
    if include_user:
        values = [row.user_name, row.user_email, *values]
    return [csv_safe(v) for v in values]


def csv_response(
    rows: AsyncIterator[Any], filename: str, include_user: bool = False
) -> StreamingResponse:
    async def generate() -> AsyncIterator[bytes]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        # BOM so Excel opens the UTF-8 file with the right encoding.
        header = (["nama", "email"] if include_user else []) + CSV_COLUMNS
        writer.writerow(header)
        yield ("﻿" + buffer.getvalue()).encode()
        async for row in rows:
            buffer.seek(0)
            buffer.truncate()
            writer.writerow(csv_row(row, include_user))
            yield buffer.getvalue().encode()

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/usage/export.csv")
async def export_csv(request: Request, user: CurrentUser, filters: Filters) -> StreamingResponse:
    flt = filters.build(user.id)

    async def rows() -> AsyncIterator[Any]:
        # A dedicated session: the response body streams after the request scope ends.
        async with request.app.state.sessionmaker() as session:
            async for row in usage.stream_requests(session, flt):
                yield row

    return csv_response(rows(), f"atheena-pemakaian-{flt.start}-{flt.end}.csv")


class FacetsOut(BaseModel):
    models: list[str]
    projects: list[str]


@router.get("/usage/facets")
async def get_facets(user: CurrentUser, session: SessionDep) -> FacetsOut:
    since = usage.today_wib() - timedelta(days=usage.MAX_RANGE_DAYS - 1)
    models, projects = await usage.facets(session, user.id, since)
    return FacetsOut(models=models, projects=projects)


class ClientConfig(BaseModel):
    api_base_url: str


@router.get("/config")
async def client_config(request: Request, user: CurrentUser) -> ClientConfig:
    settings: Settings = request.app.state.settings
    return ClientConfig(api_base_url=settings.public_api_base_url.rstrip("/"))
