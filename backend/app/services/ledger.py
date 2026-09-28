"""The only way balances change (PRD §4.3.6, FR-5.1, FR-5.2).

Every entry locks the user row, appends to ledger_entries, and updates users.balance_idr in
the caller's transaction, so the balance column always equals the ledger sum.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ids import new_id
from app.models import LedgerEntry, User

# Upper bound for a single manual entry; guards against an extra zero typed by an admin.
MAX_MANUAL_AMOUNT_IDR = 100_000_000


class LedgerError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class PostedEntry:
    entry_id: uuid.UUID
    balance_before_idr: int
    balance_after_idr: int


async def post_entry(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    entry_type: str,
    amount_idr: int,
    note: str | None = None,
    created_by: uuid.UUID | None = None,
    request_id: uuid.UUID | None = None,
) -> PostedEntry:
    """Append one ledger entry and move the balance by amount_idr (credit > 0, debit < 0)."""
    if entry_type in ("topup", "refund") and amount_idr <= 0:
        raise LedgerError("invalid_amount", "Nominal harus lebih dari 0.")
    if entry_type == "usage" and amount_idr > 0:
        raise LedgerError("invalid_amount", "Pemakaian harus berupa debit.")
    if entry_type == "adjustment":
        if amount_idr == 0:
            raise LedgerError("invalid_amount", "Nominal penyesuaian tidak boleh 0.")
        if not note or not note.strip():
            raise LedgerError("note_required", "Penyesuaian wajib disertai alasan.")
    if entry_type not in ("topup", "usage", "adjustment", "refund"):
        raise LedgerError("invalid_type", "Jenis entri tidak dikenal.")

    balance = await session.scalar(
        select(User.balance_idr).where(User.id == user_id).with_for_update()
    )
    if balance is None:
        raise LedgerError("user_not_found", "User tidak ditemukan.")
    new_balance = balance + amount_idr
    entry_id = new_id()
    await session.execute(update(User).where(User.id == user_id).values(balance_idr=new_balance))
    await session.execute(
        insert(LedgerEntry).values(
            id=entry_id,
            user_id=user_id,
            type=entry_type,
            amount_idr=amount_idr,
            balance_after_idr=new_balance,
            request_id=request_id,
            note=note.strip() if note else None,
            created_by=created_by,
        )
    )
    return PostedEntry(entry_id=entry_id, balance_before_idr=balance, balance_after_idr=new_balance)
