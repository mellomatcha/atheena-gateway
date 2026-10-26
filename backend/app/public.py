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
# Owner's retail policy, 2026-10-27. Provider metadata stays unchanged.
REFERENCE_MULTIPLIER = Decimal("0.79")
BASE_MODELS = frozenset(
    {
        "deepseek-v4.1-flash",
        "deepseek-v4.1-flash-sg",
        "glm-5.3",
        "hy4-preview",
        "gpt-5.6-luna",
        "gemini-3.5-flash",
    }
)
HIDDEN_MODELS = frozenset({"deepseek-v4.1-flash-sg"})
CUSTOM_PRICES = {
    "gpt-5.6-sol": {"daily": 30_000, "weekly": 54_900},
    "gpt-6-astra": {"daily": 39_000, "weekly": 64_900},
}
BONUS_MODELS = ("gpt-5.6-luna", "deepseek-v4.1-flash")


def available_plans(model_id: str) -> list[Plan]:
    return [p for p in PLANS if model_id not in CUSTOM_PRICES or p["id"] in CUSTOM_PRICES[model_id]]


def retail_factor(model_id: str, provider_multiplier: str) -> Decimal:
    if model_id in BASE_MODELS:
        return Decimal(1)
    relative = Decimal(provider_multiplier) / REFERENCE_MULTIPLIER
    return Decimal("0.45") if relative < 1 else relative


def rounded_price(value: Decimal) -> int:
    return int((value / 100).to_integral_value(rounding=ROUND_CEILING)) * 100


def quote(model_id: str, plan_id: str, tokens: int | None, promo: bool = True) -> dict[str, object]:
    model = next((m for m in CATALOG["models"] if m["id"] == model_id), None)
    plan = next((p for p in available_plans(model_id) if p["id"] == plan_id), None)
    if model is None or plan is None or model_id in HIDDEN_MODELS:
        raise HTTPException(404, "Model atau paket tidak ditemukan.")
    multiplier = Decimal(model["multiplier"])
    factor = retail_factor(model_id, model["multiplier"])
    custom_price = CUSTOM_PRICES.get(model_id, {}).get(plan_id)
    included = 50_000_000 if custom_price is not None else int(plan["tokens"])
    price = (
        custom_price
        if custom_price is not None
        else rounded_price(Decimal(plan["price_idr"] if promo else plan["regular_idr"]) * factor)
    )
    regular = (
        custom_price
        if custom_price is not None
        else rounded_price(Decimal(plan["regular_idr"]) * factor)
    )
    bonus_tokens = 50_000_000 if custom_price is not None and plan_id == "weekly" else 0
    target = tokens if tokens is not None else included
    if target <= 0 or target > 1_000_000_000_000:
        raise HTTPException(422, "Jumlah token di luar batas simulasi.")
    packs = (target + included - 1) // included
    return {
        "model": model_id,
        "plan": plan_id,
        "days": plan["days"],
        "included_tokens": included,
        "price_idr": price,
        "regular_idr": regular,
        "bonus_tokens": bonus_tokens,
        "bonus_models": list(BONUS_MODELS) if bonus_tokens else [],
        "bonus_pool": "shared" if bonus_tokens else None,
        "provider_multiplier": str(multiplier),
        "multiplier": str(factor),
        "relative_factor": str(factor),
        "packs": packs,
        "total_idr": price * packs,
        "target_tokens": target,
        "effective_idr_per_million": str(Decimal(price) * 1_000_000 / included),
        "status": "published",
        "checkout_enabled": False,
        "method": "fixed-model-package" if custom_price is not None else "atheena-retail-factor",
    }


@router.get("/catalog")
async def get_catalog() -> dict[str, object]:
    return {
        **CATALOG,
        "models": [
            {
                **model,
                "provider_multiplier": model["multiplier"],
                "multiplier": str(retail_factor(model["id"], model["multiplier"])),
                "pricing_method": (
                    "fixed-model-package"
                    if model["id"] in CUSTOM_PRICES
                    else "atheena-retail-factor"
                ),
            }
            for model in CATALOG["models"]
            if model["id"] not in HIDDEN_MODELS
        ],
        "plans": PLANS,
        "offers": [
            quote(model["id"], plan["id"], None)
            for model in CATALOG["models"]
            if model["id"] not in HIDDEN_MODELS
            for plan in available_plans(model["id"])
        ],
        "checkout_enabled": False,
        "reference_model": "glm-5.3",
        "reference_multiplier": str(REFERENCE_MULTIPLIER),
        "pricing_policy_date": "2026-10-27",
    }


@router.get("/quote")
async def get_quote(
    model: str = Query(max_length=100),
    plan: Literal["daily", "weekly", "monthly"] = "monthly",
    tokens: int | None = Query(default=None, ge=1, le=1_000_000_000_000),
    promo: bool = True,
) -> dict[str, object]:
    return quote(model, plan, tokens, promo)
