"""Member balance history and top-up instructions (§8: GET /ledger; FR-5.3, FR-6.6)."""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel
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


@router.get("/topup-info")
async def topup_info(request: Request, user: CurrentUser) -> TopupInfo:
    settings: Settings = request.app.state.settings
    return TopupInfo(
        whatsapp_number=settings.topup_whatsapp_number, qris_image_path=settings.topup_qris_path
    )
