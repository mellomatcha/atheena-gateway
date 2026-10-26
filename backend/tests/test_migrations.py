import asyncio
from datetime import UTC, datetime

from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.ids import new_id
from tests.conftest import TEST_DATABASE_URL, alembic_config

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


def test_username_upgrade_preserves_existing_profile_without_exposing_name() -> None:
    config = alembic_config()
    user_id = new_id()

    async def before() -> None:
        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            await conn.execute(
                text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, :name)"),
                {
                    "id": user_id,
                    "email": f"migration-{user_id}@example.test",
                    "name": "Private Name",
                },
            )
        await engine.dispose()

    async def after() -> None:
        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            row = (
                await conn.execute(
                    text("SELECT username, display_name FROM users WHERE id=:id"), {"id": user_id}
                )
            ).one()
            assert row.display_name == "Private Name"
            assert row.username.startswith("ath_") and len(row.username) == 24
            assert "private" not in row.username.lower()
            await conn.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
        await engine.dispose()

    command.downgrade(config, "0001")
    try:
        asyncio.run(before())
    finally:
        command.upgrade(config, "head")
    asyncio.run(after())


def test_profile_setup_upgrade_preserves_chosen_username() -> None:
    config = alembic_config()
    chosen, generated = new_id(), new_id()

    async def before() -> None:
        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            for user_id, username in [(chosen, "existing_member"), (generated, "ath_" + "a" * 20)]:
                await conn.execute(
                    text(
                        "INSERT INTO users (id,email,display_name,username) "
                        "VALUES (:id,:email,'Private',:username)"
                    ),
                    {
                        "id": user_id,
                        "email": f"migration-{user_id}@example.test",
                        "username": username,
                    },
                )
        await engine.dispose()

    async def after() -> None:
        engine = create_async_engine(TEST_DATABASE_URL)
        async with engine.begin() as conn:
            for user_id, expected in [(chosen, True), (generated, False)]:
                assert (
                    await conn.scalar(
                        text("SELECT profile_completed FROM users WHERE id=:id"), {"id": user_id}
                    )
                    is expected
                )
                await conn.execute(text("DELETE FROM users WHERE id=:id"), {"id": user_id})
        await engine.dispose()

    command.downgrade(config, "0002_public_usernames")
    try:
        asyncio.run(before())
    finally:
        command.upgrade(config, "head")
    asyncio.run(after())
