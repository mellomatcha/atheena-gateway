from datetime import UTC, datetime

from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.ids import new_id
from tests.conftest import alembic_config

PRD_TABLES = {
    "users",
    "api_keys",
    "models",
    "requests",
    "ledger_entries",
    "topup_requests",
    "projects",
    "audit_logs",
    "settings",
    "usage_daily",
}


async def test_all_prd_tables_exist(db: AsyncConnection) -> None:
    rows = await db.execute(
        text(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
            " WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND NOT c.relispartition"
        )
    )
    assert set(rows.scalars()) >= PRD_TABLES


async def test_minimum_indexes_exist(db: AsyncConnection) -> None:
    rows = await db.execute(
        text("SELECT tablename, indexdef FROM pg_indexes WHERE schemaname = 'public'")
    )
    definitions = {(table, indexdef.split(" USING btree ")[1]) for table, indexdef in rows}
    assert {
        ("requests", "(user_id, started_at)"),
        ("requests", "(model_id, started_at)"),
        ("requests", "(project, started_at)"),
        ("ledger_entries", "(user_id, created_at)"),
        ("api_keys", "(key_hash)"),
    } <= definitions


async def test_requests_rows_route_to_monthly_partition(db: AsyncConnection) -> None:
    now = datetime.now(UTC)
    await db.execute(
        text(
            "INSERT INTO requests (id, request_id, started_at, endpoint, status_code)"
            " VALUES (:id, :request_id, :started_at, '/v1/chat/completions', 200)"
        ),
        {"id": new_id(), "request_id": new_id(), "started_at": now},
    )
    partition = await db.scalar(text("SELECT tableoid::regclass::text FROM requests"))
    assert partition == f"requests_{now:%Y_%m}"


async def test_requests_outside_created_months_fall_into_default(db: AsyncConnection) -> None:
    row_id = new_id()
    await db.execute(
        text(
            "INSERT INTO requests (id, request_id, started_at, endpoint, status_code)"
            " VALUES (:id, :request_id, '2030-01-15T00:00:00Z', '/v1/messages', 200)"
        ),
        {"id": row_id, "request_id": new_id()},
    )
    partition = await db.scalar(
        text("SELECT tableoid::regclass::text FROM requests WHERE id = :id"), {"id": row_id}
    )
    assert partition == "requests_default"


def test_downgrade_and_upgrade_roundtrip() -> None:
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    command.check(config)
