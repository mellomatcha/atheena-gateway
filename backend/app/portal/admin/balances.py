"""Manual top-ups and adjustments by an admin (FR-5.3 step 4, FR-7.1, FR-7.2, FR-7.7)."""

import uuid
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from app.models import User
from app.net import client_ip_hash
from app.portal.deps import AdminUser, PortalError, SessionDep
from app.portal.ledger import LedgerKind, LedgerPage, ledger_page
from app.services.audit import record_audit
from app.services.ledger import MAX_MANUAL_AMOUNT_IDR, LedgerError, post_entry

router = APIRouter()


class UserSummary(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    tier: str
    status: str
    balance_idr: int


class BalanceEntryIn(BaseModel):
    type: Literal["topup", "adjustment"]
    # Top-ups are credits; adjustments may credit (positive) or debit (negative).
    amount_idr: int = Field(ge=-MAX_MANUAL_AMOUNT_IDR, le=MAX_MANUAL_AMOUNT_IDR)
    note: str | None = Field(default=None, max_length=500)


class BalanceEntryOut(BaseModel):
    entry_id: uuid.UUID
    user: UserSummary
    balance_before_idr: int
    balance_after_idr: int


@router.get("/users")
async def list_users(
    admin: AdminUser, session: SessionDep, q: str | None = Query(None, max_length=100)
) -> list[UserSummary]:
    query = select(User).order_by(User.display_name, User.email).limit(200)
    if q and q.strip():
        term = q.strip()
        query = query.where(
            or_(
                User.email.icontains(term, autoescape=True),
                User.display_name.icontains(term, autoescape=True),
            )
        )
    users = (await session.scalars(query)).all()
    return [UserSummary.model_validate(u, from_attributes=True) for u in users]


@router.post("/users/{user_id}/adjustments", status_code=201)
async def add_balance_entry(
    user_id: uuid.UUID,
    body: BalanceEntryIn,
    request: Request,
    admin: AdminUser,
    session: SessionDep,
) -> BalanceEntryOut:
    if body.type == "topup" and body.amount_idr <= 0:
        raise PortalError(400, "invalid_amount", "Nominal top-up harus lebih dari 0.")
    try:
        posted = await post_entry(
            session,
            user_id=user_id,
            entry_type=body.type,
            amount_idr=body.amount_idr,
            note=body.note,
            created_by=admin.id,
        )
    except LedgerError as exc:
        status = 404 if exc.code == "user_not_found" else 400
        raise PortalError(status, exc.code, exc.message) from exc
    await record_audit(
        session,
        actor_user_id=admin.id,
        action=f"balance.{body.type}",
        target_type="user",
        target_id=str(user_id),
        before={"balance_idr": posted.balance_before_idr},
        after={
            "balance_idr": posted.balance_after_idr,
            "amount_idr": body.amount_idr,
            "ledger_entry_id": str(posted.entry_id),
            "note": body.note,
        },
        ip_hash=client_ip_hash(request),
    )
    await session.commit()
    user = await session.get(User, user_id)
    return BalanceEntryOut(
        entry_id=posted.entry_id,
        user=UserSummary.model_validate(user, from_attributes=True),
        balance_before_idr=posted.balance_before_idr,
        balance_after_idr=posted.balance_after_idr,
    )


@router.get("/users/{user_id}/ledger")
async def user_ledger(
    user_id: uuid.UUID,
    admin: AdminUser,
    session: SessionDep,
    page: int = Query(1, ge=1, le=10_000),
    kind: LedgerKind = "all",
) -> LedgerPage:
    if await session.get(User, user_id) is None:
        raise PortalError(404, "user_not_found", "User tidak ditemukan.")
    return await ledger_page(session, user_id, page, kind)
