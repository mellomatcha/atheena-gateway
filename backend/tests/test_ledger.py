"""Schema guarantees for the money ledger (PRD §4.3.6, FR-5.2)."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from app.ids import new_id


async def create_user(db: AsyncConnection) -> uuid.UUID:
    user_id = new_id()
    await db.execute(
        text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, 'Test User')"),
        {"id": user_id, "email": f"user-{user_id}@example.test"},
    )
    return user_id


async def insert_entry(
    db: AsyncConnection,
    user_id: uuid.UUID,
    entry_type: str,
    amount: int,
    note: str | None = None,
) -> uuid.UUID:
    entry_id = new_id()
    await db.execute(
        text(
            "INSERT INTO ledger_entries (id, user_id, type, amount_idr, balance_after_idr, note)"
            " VALUES (:id, :user_id, :type, :amount, :amount, :note)"
        ),
        {"id": entry_id, "user_id": user_id, "type": entry_type, "amount": amount, "note": note},
    )
    return entry_id


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE ledger_entries SET amount_idr = 1 WHERE id = :id",
        "UPDATE ledger_entries SET note = 'edited' WHERE id = :id",
        "DELETE FROM ledger_entries WHERE id = :id",
    ],
)
async def test_ledger_rejects_update_and_delete(db: AsyncConnection, statement: str) -> None:
    user_id = await create_user(db)
    entry_id = await insert_entry(db, user_id, "topup", 50_000)

    savepoint = await db.begin_nested()
    with pytest.raises(DBAPIError, match="ledger_entries is append-only"):
        await db.execute(text(statement), {"id": entry_id})
    await savepoint.rollback()

    amount = await db.scalar(
        text("SELECT amount_idr FROM ledger_entries WHERE id = :id"), {"id": entry_id}
    )
    assert amount == 50_000


async def test_ledger_rejects_truncate(db: AsyncConnection) -> None:
    user_id = await create_user(db)
    await insert_entry(db, user_id, "topup", 10_000)

    savepoint = await db.begin_nested()
    with pytest.raises(DBAPIError, match="TRUNCATE is not allowed"):
        await db.execute(text("TRUNCATE ledger_entries CASCADE"))
    await savepoint.rollback()

    count = await db.scalar(
        text("SELECT count(*) FROM ledger_entries WHERE user_id = :id"), {"id": user_id}
    )
    assert count == 1


async def test_ledger_allows_inserts(db: AsyncConnection) -> None:
    user_id = await create_user(db)
    await insert_entry(db, user_id, "topup", 100_000)
    await insert_entry(db, user_id, "usage", -1_250)
    await insert_entry(db, user_id, "adjustment", -500, note="salah input top-up")
    await insert_entry(db, user_id, "refund", 1_250)

    total = await db.scalar(
        text("SELECT sum(amount_idr) FROM ledger_entries WHERE user_id = :id"), {"id": user_id}
    )
    assert total == 99_500


@pytest.mark.parametrize(
    ("entry_type", "amount", "note"),
    [
        ("topup", 0, None),
        ("topup", -1, None),
        ("refund", -1, None),
        ("usage", 1, None),
        ("adjustment", 1_000, None),
        ("adjustment", 1_000, "   "),
        ("bonus", 1_000, None),
    ],
)
async def test_ledger_rejects_invalid_entries(
    db: AsyncConnection, entry_type: str, amount: int, note: str | None
) -> None:
    user_id = await create_user(db)
    savepoint = await db.begin_nested()
    with pytest.raises(IntegrityError):
        await insert_entry(db, user_id, entry_type, amount, note)
    await savepoint.rollback()
