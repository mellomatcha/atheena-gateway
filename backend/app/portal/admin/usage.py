"""Global usage for admins (§8 admin /usage/*; FR-7.3, FR-7.4)."""

import csv
import io
import re
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.portal.deps import AdminUser, PortalError, SessionDep
from app.portal.usage import (
    FilterParams,
    RequestPage,
    TimeseriesOut,
    TotalsOut,
    build_request_page,
    build_timeseries,
    csv_response,
    csv_safe,
)
from app.services import reports, usage
from app.services.usage import UsageFilter

router = APIRouter()

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def admin_filters(
    base: Annotated[FilterParams, Depends()], user: uuid.UUID | None = None
) -> UsageFilter:
    return base.build(user)


AdminFilter = Annotated[UsageFilter, Depends(admin_filters)]


class BreakdownOut(BaseModel):
    key: str | None
    label: str
    totals: TotalsOut


class AdminSummaryOut(BaseModel):
    totals: TotalsOut
    by_user: list[BreakdownOut]
    by_model: list[BreakdownOut]
    by_project: list[BreakdownOut]
    by_provider: list[BreakdownOut]


def _rows(rows: list[reports.BreakdownRow]) -> list[BreakdownOut]:
    return [BreakdownOut(key=r.key, label=r.label, totals=TotalsOut.of(r.totals)) for r in rows]


@router.get("/usage/summary")
async def admin_summary(admin: AdminUser, session: SessionDep, flt: AdminFilter) -> AdminSummaryOut:
    return AdminSummaryOut(
        totals=TotalsOut.of(await usage.totals(session, flt)),
        by_user=_rows(await reports.breakdown(session, flt, "user")),
        by_model=_rows(await reports.breakdown(session, flt, "model")),
        by_project=_rows(await reports.breakdown(session, flt, "project")),
        by_provider=_rows(await reports.breakdown(session, flt, "provider")),
    )


@router.get("/usage/timeseries")
async def admin_timeseries(
    admin: AdminUser,
    session: SessionDep,
    flt: AdminFilter,
    unit: Literal["token", "idr"] = "idr",
) -> TimeseriesOut:
    return await build_timeseries(session, flt, unit)


@router.get("/usage/requests")
async def admin_requests(
    admin: AdminUser,
    session: SessionDep,
    flt: AdminFilter,
    page: int = Query(1, ge=1, le=100_000),
) -> RequestPage:
    return await build_request_page(session, flt, page, include_user=True)


@router.get("/usage/export.csv")
async def admin_export(request: Request, admin: AdminUser, flt: AdminFilter) -> StreamingResponse:
    async def rows() -> AsyncIterator[Any]:
        async with request.app.state.sessionmaker() as session:
            async for row in usage.stream_requests(session, flt):
                yield row

    return csv_response(
        rows(), f"atheena-pemakaian-semua-{flt.start}-{flt.end}.csv", include_user=True
    )


class MonthlyReportOut(BaseModel):
    month: str
    by: Literal["project", "user"]
    rows: list[BreakdownOut]
    totals: TotalsOut


def _check_month(month: str) -> str:
    if not MONTH_PATTERN.match(month):
        raise PortalError(400, "invalid_month", "Format bulan harus YYYY-MM.")
    return month


@router.get("/reports/monthly")
async def monthly(
    admin: AdminUser,
    session: SessionDep,
    month: str = Query(..., max_length=7),
    by: Literal["project", "user"] = "project",
) -> MonthlyReportOut:
    month = _check_month(month)
    rows = await reports.monthly_report(session, month, by)
    return MonthlyReportOut(
        month=month,
        by=by,
        rows=_rows(rows),
        totals=TotalsOut.of(await usage.totals(session, reports.month_filter(month))),
    )


@router.get("/reports/monthly.csv")
async def monthly_csv(
    admin: AdminUser,
    session: SessionDep,
    month: str = Query(..., max_length=7),
    by: Literal["project", "user"] = "project",
) -> StreamingResponse:
    month = _check_month(month)
    rows = await reports.monthly_report(session, month, by)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "bulan",
            "proyek" if by == "project" else "pengguna",
            "request",
            "input_tokens",
            "output_tokens",
            "cache_write_tokens",
            "cache_read_tokens",
            "total_tokens",
            "biaya_idr",
        ]
    )
    for row in rows:
        t = row.totals
        writer.writerow(
            [
                month,
                csv_safe(row.label),
                t.requests,
                t.input_tokens,
                t.output_tokens,
                t.cache_write_tokens,
                t.cache_read_tokens,
                t.tokens,
                t.cost_idr,
            ]
        )
    body = "﻿" + buffer.getvalue()

    async def once() -> AsyncIterator[bytes]:
        yield body.encode()

    return StreamingResponse(
        once(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="atheena-laporan-{month}-per-{by}.csv"'
        },
    )
