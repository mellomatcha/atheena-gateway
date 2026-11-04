"""Member balance history and top-up instructions (§8: GET /ledger; FR-5.3, FR-6.6)."""

import uuid
from datetime import datetime
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import LedgerEntry
from app.portal.deps import CurrentUser, SessionDep

router = APIRouter()

PAGE_SIZE = 50
CREDIT_TYPES = ("topup", "adjustment", "refund")

LedgerKind = Literal["all", "credits"]


class LedgerEntryOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    type: str
    amount_idr: int
    balance_after_idr: int
    note: str | None
    request_id: uuid.UUID | None


class LedgerPage(BaseModel):
    items: list[LedgerEntryOut]
    page: int
    page_size: int
    total: int


async def ledger_page(
    session: AsyncSession, user_id: uuid.UUID, page: int, kind: LedgerKind
) -> LedgerPage:
    conditions = [LedgerEntry.user_id == user_id]
    if kind == "credits":
        conditions.append(LedgerEntry.type.in_(CREDIT_TYPES))
    total = await session.scalar(select(func.count()).where(*conditions))
    rows = (
        await session.scalars(
            select(LedgerEntry)
            .where(*conditions)
            .order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        )
    ).all()
    return LedgerPage(
        items=[LedgerEntryOut.model_validate(row, from_attributes=True) for row in rows],
        page=page,
        page_size=PAGE_SIZE,
        total=int(total or 0),
    )


@router.get("/ledger")
async def get_ledger(
    user: CurrentUser,
    session: SessionDep,
    page: int = Query(1, ge=1, le=10_000),
    kind: LedgerKind = "all",
) -> LedgerPage:
    return await ledger_page(session, user.id, page, kind)


class TopupInfo(BaseModel):
    whatsapp_number: str
    qris_image_path: str
    payments_enabled: bool


@router.get("/topup-info")
async def topup_info(request: Request, user: CurrentUser) -> TopupInfo:
    settings: Settings = request.app.state.settings
    return TopupInfo(
        whatsapp_number=settings.topup_whatsapp_number,
        qris_image_path=settings.topup_qris_path,
        payments_enabled=settings.topup_enabled,
    )


class TopupQuoteIn(BaseModel):
    amount_idr: int = Field(strict=True, ge=1000, le=100_000_000)
    method: Literal[
        "BCA",
        "Mandiri",
        "BRI",
        "BNI",
        "BSI",
        "Bank lainnya",
        "DANA",
        "GoPay",
        "OVO",
        "ShopeePay",
        "LinkAja",
        "E-wallet lainnya",
    ]


@router.post("/topup/quote")
async def topup_quote(body: TopupQuoteIn, user: CurrentUser) -> dict[str, object]:
    """Prepare a manual request. Never create a payment or credit the ledger."""
    amount = f"Rp{body.amount_idr:,}".replace(",", ".")
    message = "\n".join(
        [
            "Halo admin ATHEENA, saya ingin top-up saldo.",
            f"Username: {user.username or user.display_name}",
            f"Email akun: {user.email}",
            f"Nominal: {amount}",
            f"Metode yang ingin saya gunakan: {body.method}",
            "Mohon kirim instruksi pembayaran. Terima kasih.",
        ]
    )
    return {
        "amount_idr": body.amount_idr,
        "balance_after_idr": user.balance_idr + body.amount_idr,
        "method": body.method,
        "message": message,
        "whatsapp_url": "https://wa.me/6282312202002?text=" + quote(message, safe=""),
        "status": "awaiting_contact",
    }
