"""Member usage views and the daily rollup worker (FR-6.1 to FR-6.4, FR-6.8, PRD §7)."""

import csv
import io
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

import httpx
from sqlalchemy import text

from app.services.usage import today_wib
from app.worker import ROLLUP_LOCK_KEY, ensure_partitions, rollup_days, run_once
from tests.conftest import ClientFactory
from tests.gateway_support import GatewayData, gateway_data

WIB_OFFSET = timedelta(hours=7)


def wib(y: int, m: int, d: int, hh: int, mm: int = 0) -> datetime:
    """A WIB wall-clock time as an aware UTC datetime."""
    return datetime(y, m, d, hh, mm, tzinfo=UTC) - WIB_OFFSET


def email_of(user_id: uuid.UUID) -> str:
    return f"u-{user_id}@example.test"


@asynccontextmanager
async def as_user(
    gateway_factory: ClientFactory, user_id: uuid.UUID
) -> AsyncIterator[httpx.AsyncClient]:
    async with gateway_factory(app_env="development", dev_auth_email=email_of(user_id)) as client:
        client.headers.update({"X-Atheena-CSRF": "1"})
        yield client


async def seed_usage(data: GatewayData) -> dict[str, object]:
    """Two users, two models, two keys, a project, successes and failures around WIB midnight."""
    user = await data.user()
    other = await data.user()
    key_a, key_a_id = await data.key(user)
    _, key_b_id = await data.key(user)
    m1 = await data.model()
    m2 = await data.model()
    rows = [
        # 23:30 WIB on 10 Aug belongs to 10 Aug even though it is 16:30 UTC.
        dict(started_at=wib(2026, 8, 10, 23, 30), model=m1, api_key_id=key_a_id, cost_idr=100),
        # 00:30 WIB on 11 Aug is still 10 Aug in UTC but belongs to 11 Aug.
        dict(
            started_at=wib(2026, 8, 11, 0, 30),
            model=m1,
            api_key_id=key_a_id,
            cost_idr=200,
            project="helios",
        ),
        dict(
            started_at=wib(2026, 8, 11, 12, 0),
            model=m2,
            api_key_id=key_b_id,
            cost_idr=400,
            tokens=(1000, 500, 10, 90),
        ),
        dict(
            started_at=wib(2026, 8, 12, 9, 0),
            model=m2,
            api_key_id=key_b_id,
            cost_idr=0,
            status_code=429,
            tokens=(0, 0, 0, 0),
        ),
    ]
    for row in rows:
        await data.request(user_id=user, **row)  # type: ignore[arg-type]
    # Another user's usage on the same days must never show up.
    await data.request(user_id=other, started_at=wib(2026, 8, 11, 10, 0), model=m1, cost_idr=9999)
    return {
        "user": user,
        "key_a": key_a,
        "key_a_id": key_a_id,
        "key_b_id": key_b_id,
        "m1": m1,
        "m2": m2,
    }


RANGE = {"from": "2026-08-09", "to": "2026-08-12"}


async def test_timeseries_uses_wib_days_and_fills_gaps(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        s = await seed_usage(data)
        async with as_user(gateway_factory, s["user"]) as client:  # type: ignore[arg-type]
            idr = (await client.get("/app/api/usage/timeseries", params=RANGE)).json()
            tok = (
                await client.get("/app/api/usage/timeseries", params={**RANGE, "unit": "token"})
            ).json()
    assert [p["day"] for p in idr["points"]] == [
        "2026-08-09",
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
    ]
    assert [p["value"] for p in idr["points"]] == [0, 100, 600, 0]
    assert [p["totals"]["requests"] for p in idr["points"]] == [0, 1, 2, 1]
    assert [p["value"] for p in tok["points"]] == [0, 150, 150 + 1600, 0]
    assert idr["range_totals"]["cost_idr"] == 700
    assert idr["range_totals"]["requests"] == 4


async def test_chart_totals_match_request_log(gateway_factory: ClientFactory) -> None:
    """Tahap 4 acceptance: chart numbers equal the sum of the log table, for every filter."""
    async with gateway_data() as data:
        s = await seed_usage(data)
        filters = [
            {},
            {"model": s["m1"]},
            {"key": str(s["key_b_id"])},
            {"project": "helios"},
            {"project": "none"},
            {"status": "success"},
            {"status": "failed"},
        ]
        async with as_user(gateway_factory, s["user"]) as client:  # type: ignore[arg-type]
            for extra in filters:
                params = {**RANGE, **extra}
                series = (await client.get("/app/api/usage/timeseries", params=params)).json()
                log = (await client.get("/app/api/usage/requests", params=params)).json()
                assert sum(p["value"] for p in series["points"]) == sum(
                    r["cost_idr"] for r in log["items"]
                ), extra
                assert sum(p["totals"]["requests"] for p in series["points"]) == log["total"]
                assert series["range_totals"]["requests"] == log["total"]


async def test_filters_select_the_right_rows(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        s = await seed_usage(data)
        async with as_user(gateway_factory, s["user"]) as client:  # type: ignore[arg-type]

            async def costs(**extra: str) -> list[int]:
                response = await client.get("/app/api/usage/requests", params={**RANGE, **extra})
                return sorted(r["cost_idr"] for r in response.json()["items"])

            assert await costs() == [0, 100, 200, 400]
            assert await costs(model=s["m1"]) == [100, 200]  # type: ignore[arg-type]
            assert await costs(key=str(s["key_b_id"])) == [0, 400]
            assert await costs(project="helios") == [200]
            assert await costs(project="none") == [0, 100, 400]
            assert await costs(status="failed") == [0]
            assert await costs(status="success") == [100, 200, 400]
            log = (await client.get("/app/api/usage/requests", params=RANGE)).json()
    first = log["items"][0]
    assert first["status_code"] == 429
    assert first["key_name"] == "test"
    assert first["key_prefix"].startswith("sk-ath-")
    assert first["user_id"] is None  # member view never carries user fields
    assert all(r["cost_idr"] != 9999 for r in log["items"])


async def test_request_log_paginates(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user = await data.user()
        model = await data.model()
        for i in range(55):
            await data.request(
                user_id=user,
                started_at=wib(2026, 8, 20, 8) + timedelta(minutes=i),
                model=model,
                cost_idr=i,
            )
        async with as_user(gateway_factory, user) as client:
            params = {"from": "2026-08-20", "to": "2026-08-20"}
            first = (await client.get("/app/api/usage/requests", params=params)).json()
            second = (
                await client.get("/app/api/usage/requests", params={**params, "page": 2})
            ).json()
    assert first["total"] == 55
    assert len(first["items"]) == 50 and len(second["items"]) == 5
    assert first["items"][0]["cost_idr"] == 54  # newest first
    assert second["items"][-1]["cost_idr"] == 0


async def test_summary_windows_and_top_model(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user = await data.user(balance=42_000)
        busy = await data.model()
        rare = await data.model()
        now = datetime.now(UTC)
        await data.request(
            user_id=user, started_at=now - timedelta(minutes=5), model=busy, cost_idr=10
        )
        await data.request(
            user_id=user, started_at=now - timedelta(days=3), model=busy, cost_idr=20
        )
        await data.request(
            user_id=user, started_at=now - timedelta(days=20), model=rare, cost_idr=40
        )
        await data.request(
            user_id=user, started_at=now - timedelta(days=45), model=rare, cost_idr=80
        )
        async with as_user(gateway_factory, user) as client:
            summary = (await client.get("/app/api/usage/summary")).json()
    assert summary["balance_idr"] == 42_000
    assert summary["today"]["cost_idr"] in (10, 0)  # 0 only if run across WIB midnight
    assert summary["last_7_days"]["cost_idr"] == 30
    assert summary["last_30_days"]["cost_idr"] == 70
    assert summary["last_30_days"]["requests"] == 3
    assert summary["top_model_30_days"] == busy


async def test_invalid_ranges_are_rejected(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user = await data.user()
        async with as_user(gateway_factory, user) as client:
            reversed_range = await client.get(
                "/app/api/usage/timeseries", params={"from": "2026-08-10", "to": "2026-08-01"}
            )
            too_long = await client.get(
                "/app/api/usage/timeseries", params={"from": "2025-01-01", "to": "2026-08-01"}
            )
            default = await client.get("/app/api/usage/timeseries")
    assert reversed_range.status_code == 400
    assert too_long.status_code == 400
    assert len(default.json()["points"]) == 30
    assert default.json()["end"] == today_wib().isoformat()


async def test_csv_export_is_scoped_and_formula_safe(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user = await data.user()
        other = await data.user()
        model = await data.model()
        await data.request(
            user_id=user,
            started_at=wib(2026, 8, 15, 23, 59),
            model=model,
            project='=HYPERLINK("http://evil")',
            cost_idr=123,
        )
        await data.request(
            user_id=user, started_at=wib(2026, 8, 15, 10), model=model, project="+cmd", cost_idr=1
        )
        await data.request(
            user_id=other, started_at=wib(2026, 8, 15, 11), model=model, cost_idr=777
        )
        async with as_user(gateway_factory, user) as client:
            response = await client.get(
                "/app/api/usage/export.csv", params={"from": "2026-08-15", "to": "2026-08-15"}
            )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "atheena-pemakaian-2026-08-15-2026-08-15.csv" in response.headers["content-disposition"]
    body = response.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(body)))
    assert rows[0][:3] == ["waktu_wib", "request_id", "model"]
    assert len(rows) == 3  # header + this user's two requests only
    first = dict(zip(rows[0], rows[1], strict=True))
    assert first["waktu_wib"] == "2026-08-15 23:59:00"
    assert first["proyek"].startswith("'=")  # neutralized formula (CSV injection)
    assert first["biaya_idr"] == "123"
    assert dict(zip(rows[0], rows[2], strict=True))["proyek"] == "'+cmd"
    assert "777" not in body


async def test_facets_and_config(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user = await data.user()
        model = await data.model()
        await data.request(
            user_id=user,
            started_at=datetime.now(UTC) - timedelta(days=2),
            model=model,
            project="riset",
        )
        async with as_user(gateway_factory, user) as client:
            facets = (await client.get("/app/api/usage/facets")).json()
            config = (await client.get("/app/api/config")).json()
    assert facets == {"models": [model], "projects": ["riset"]}
    assert config == {"api_base_url": "https://api.atheena.online/v1"}


async def test_rollup_matches_requests_and_is_idempotent() -> None:
    async with gateway_data() as data:
        s = await seed_usage(data)
        user = s["user"]
        days = [date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 12)]
        async with data.engine.begin() as conn:
            await rollup_days(conn, days)
        async with data.engine.begin() as conn:
            await rollup_days(conn, days)  # second run updates, never duplicates

        rows = await data.fetch(
            "SELECT day, project, request_count, input_tokens, output_tokens,"
            " cache_write_tokens, cache_read_tokens, cost_idr FROM usage_daily"
            " WHERE user_id = :u ORDER BY day, cost_idr",
            u=user,
        )
        summary = [(r.day.isoformat(), r.project, r.request_count, r.cost_idr) for r in rows]
        assert summary == [
            ("2026-08-10", None, 1, 100),
            ("2026-08-11", "helios", 1, 200),
            ("2026-08-11", None, 1, 400),
            ("2026-08-12", None, 1, 0),
        ]
        assert rows[2].cache_read_tokens == 90 and rows[2].cache_write_tokens == 10

        # A late request (e.g. a stream finishing after midnight) is folded in on the next run.
        await data.request(
            user_id=user, started_at=wib(2026, 8, 11, 12, 30), model=s["m2"], cost_idr=50
        )  # type: ignore[arg-type]
        async with data.engine.begin() as conn:
            await rollup_days(conn, days)
        updated = await data.fetch(
            "SELECT request_count, cost_idr FROM usage_daily WHERE user_id = :u"
            " AND day = '2026-08-11' AND project IS NULL",
            u=user,
        )
        assert [(r.request_count, r.cost_idr) for r in updated] == [(2, 450)]


async def test_worker_creates_partitions_and_respects_lock() -> None:
    async with gateway_data() as data:
        async with data.engine.begin() as conn:
            await ensure_partitions(conn, months_ahead=4)
        names = {
            r.relname
            for r in await data.fetch(
                "SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid"
                " JOIN pg_class p ON p.oid = i.inhparent WHERE p.relname = 'requests'"
            )
        }
        first_of_month = today_wib().replace(day=1)
        month = first_of_month
        for _ in range(5):
            assert f"requests_{month:%Y_%m}" in names
            month = (month + timedelta(days=32)).replace(day=1)

        # While another session holds the job lock, a run is skipped instead of racing.
        async with data.engine.connect() as holder:
            await holder.execute(text("SELECT pg_advisory_lock(:k)"), {"k": ROLLUP_LOCK_KEY})
            skipped = await run_once(data.engine)
            await holder.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ROLLUP_LOCK_KEY})
        assert skipped.skipped is True
        ran = await run_once(data.engine)
        assert ran.skipped is False
        assert ran.days[-1] == today_wib()
