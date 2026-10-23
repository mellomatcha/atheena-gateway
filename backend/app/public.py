"""Public catalog and retail package pricing. No account-cost data or billing mutations."""

import json
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Literal, TypedDict

from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/public")
CATALOG = json.loads((Path(__file__).parent / "data/codebuddy_catalog.json").read_text())


class Plan(TypedDict):
    id: str
    name: str
    days: int
    tokens: int
    price_idr: int
    regular_idr: int


PLANS: tuple[Plan, ...] = (
    {
        "id": "daily",
        "name": "Harian",
        "days": 1,
        "tokens": 100_000_000,
        "price_idr": 9900,
        "regular_idr": 9900,
    },
    {
        "id": "weekly",
        "name": "Mingguan",
        "days": 7,
        "tokens": 250_000_000,
        "price_idr": 34900,
        "regular_idr": 34900,
    },
    {
        "id": "monthly",
        "name": "Bulanan",
        "days": 30,
        "tokens": 500_000_000,
        "price_idr": 49900,
        "regular_idr": 59900,
    },
)
# Retail policy: use the paid SG variant as the nonzero relative reference. The
# base package price is the floor, including for provider models marked zero-credit.
REFERENCE_MULTIPLIER = Decimal("0.03")


def rounded_price(value: Decimal) -> int:
    return int((value / 100).to_integral_value(rounding=ROUND_CEILING)) * 100


def quote(model_id: str, plan_id: str, tokens: int | None, promo: bool = True) -> dict[str, object]:
    model = next((m for m in CATALOG["models"] if m["id"] == model_id), None)
    plan = next((p for p in PLANS if p["id"] == plan_id), None)
    if model is None or plan is None:
        raise HTTPException(404, "Model atau paket tidak ditemukan.")
    multiplier = Decimal(model["multiplier"])
    factor = max(Decimal(1), multiplier / REFERENCE_MULTIPLIER)
    price = rounded_price(Decimal(plan["price_idr"] if promo else plan["regular_idr"]) * factor)
    target = tokens if tokens is not None else int(plan["tokens"])
    if target <= 0 or target > 1_000_000_000_000:
        raise HTTPException(422, "Jumlah token di luar batas simulasi.")
    packs = (target + int(plan["tokens"]) - 1) // int(plan["tokens"])
    return {
        "model": model_id,
        "plan": plan_id,
        "days": plan["days"],
        "included_tokens": plan["tokens"],
        "price_idr": price,
        "regular_idr": rounded_price(Decimal(plan["regular_idr"]) * factor),
        "multiplier": str(multiplier),
        "relative_factor": str(factor),
        "packs": packs,
        "total_idr": price * packs,
        "target_tokens": target,
        "effective_idr_per_million": str(Decimal(price) * 1_000_000 / int(plan["tokens"])),
        "status": "published",
        "checkout_enabled": False,
        "method": "base-package"
        if multiplier <= REFERENCE_MULTIPLIER
        else "relative-multiplier-estimate",
    }


@router.get("/catalog")
async def get_catalog() -> dict[str, object]:
    return {
        **CATALOG,
        "plans": PLANS,
        "checkout_enabled": False,
        "reference_model": "deepseek-v4.1-flash-sg",
        "reference_multiplier": str(REFERENCE_MULTIPLIER),
    }


@router.get("/quote")
async def get_quote(
    model: str = Query(max_length=100),
    plan: Literal["daily", "weekly", "monthly"] = "monthly",
    tokens: int | None = Query(default=None, ge=1, le=1_000_000_000_000),
    promo: bool = True,
) -> dict[str, object]:
    return quote(model, plan, tokens, promo)
