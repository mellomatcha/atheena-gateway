"""Retail-only quotes: decimal rounding, public privacy, concurrency and validation."""

import asyncio
from decimal import Decimal

import pytest

from app.public import quote, retail_factor, rounded_price
from tests.conftest import ClientFactory


@pytest.mark.parametrize(
    ("plan", "price", "tokens"),
    [
        ("daily", 9900, 100_000_000),
        ("weekly", 34900, 250_000_000),
        ("monthly", 49900, 500_000_000),
    ],
)
def test_owner_base_prices(plan: str, price: int, tokens: int) -> None:
    result = quote("deepseek-v4.1-flash", plan, None)
    assert result["price_idr"] == price
    assert result["included_tokens"] == tokens
    assert result["packs"] == 1
    assert result["checkout_enabled"] is False
    for model in ["glm-5.3", "glm-5.2", "hy4-preview", "gpt-5.6-luna", "gemini-3.5-flash"]:
        same_tier = quote(model, plan, None)
        assert same_tier["price_idr"] == price
        assert same_tier["included_tokens"] == tokens


@pytest.mark.parametrize(
    ("model", "provider", "expected"),
    [
        ("deepseek-v4.1-flash", "0.00", Decimal(1)),
        ("glm-5.3", "0.79", Decimal(1)),
        ("glm-5.2", "0.79", Decimal(1)),
        ("glm-5.3-flash", "0.06", Decimal("0.45")),
        ("deepseek-v4.1-flash-sg", "0.03", Decimal(1)),
        ("hy3", "0.00", Decimal("0.45")),
        ("kimi-k2.8-preview", "0.77", Decimal("0.45")),
        ("kimi-k2.6", "0.52", Decimal("0.45")),
        ("gpt-6-astra", "6.67", Decimal("6.67") / Decimal("0.79")),
    ],
)
def test_retail_policy(model: str, provider: str, expected: Decimal) -> None:
    assert retail_factor(model, provider) == expected


def test_promo_rounding_and_full_package_boundaries() -> None:
    assert quote("deepseek-v4.1-flash", "monthly", None, False)["price_idr"] == 59900
    result = quote("glm-5.3-flash", "daily", 100_000_001)
    assert result["price_idr"] == 4500  # 9900 * 0.45, rounded up to Rp100
    assert result["packs"] == 2
    assert result["total_idr"] == 9000
    assert quote("gpt-5.6-luna", "daily", 1)["price_idr"] == 9900
    assert quote("gpt-6-astra", "daily", 1)["price_idr"] == 39000
    assert quote("glm-5.3-flash", "monthly", None)["price_idr"] == 22500
    assert quote("glm-5.3-flash", "monthly", None, False)["price_idr"] == 27000
    assert rounded_price(Decimal("9900.00000001")) == 10000
    assert rounded_price(Decimal("9900")) == 9900


async def test_public_catalog_has_no_account_data_or_auth_requirement(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(
        app_env="production",
        dev_auth_email="",
        cf_access_team_domain="test.cloudflareaccess.com",
        cf_access_aud="test-aud",
    ) as client:
        response = await client.get("/api/public/catalog")
        assert response.status_code == 200
        body = response.json()
        assert len(body["models"]) == 16
        assert len(body["offers"]) == 46
        assert "deepseek-v4.1-flash-sg" not in response.text
        assert len({(o["model"], o["plan"]) for o in body["offers"]}) == 46
        for offer in body["offers"]:
            assert offer == quote(offer["model"], offer["plan"], None)
        assert body["version"] == "2.173.0"
        flash = next(m for m in body["models"] if m["id"] == "deepseek-v4.1-flash")
        assert flash["multiplier"] == "1" and flash["provider_multiplier"] == "0.00"
        for forbidden in (
            "email",
            "api_key",
            "access_token",
            "refresh_token",
            "account_cost",
            "balance",
        ):
            assert forbidden not in response.text
        ids = [model["id"] for model in body["models"]]
        assert len(ids) == len(set(ids))
        responses = await asyncio.gather(
            *[
                client.get(
                    "/api/public/quote", params={"model": "deepseek-v4.1-flash", "plan": "daily"}
                )
                for _ in range(12)
            ]
        )
        assert all(r.status_code == 200 and r.json()["total_idr"] == 9900 for r in responses)


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"model": "unknown"}, 404),
        ({"model": "deepseek-v4.1-flash-sg", "plan": "daily"}, 404),
        ({"model": "gpt-5.6-sol", "plan": "monthly"}, 404),
        ({"model": "gpt-6-astra", "plan": "monthly"}, 404),
        ({"model": "deepseek-v4.1-flash", "plan": "yearly"}, 422),
        ({"model": "deepseek-v4.1-flash", "tokens": "0"}, 422),
        ({"model": "deepseek-v4.1-flash", "tokens": "-1"}, 422),
        ({"model": "deepseek-v4.1-flash", "tokens": "1.5"}, 422),
        ({"model": "deepseek-v4.1-flash", "tokens": "1000000000001"}, 422),
    ],
)
async def test_invalid_quotes(
    client_factory: ClientFactory, params: dict[str, str], status: int
) -> None:
    async with client_factory() as client:
        response = await client.get("/api/public/quote", params=params)
    assert response.status_code == status


@pytest.mark.parametrize(
    ("model", "plan", "price", "bonus"),
    [
        ("gpt-5.6-sol", "daily", 30000, 0),
        ("gpt-5.6-sol", "weekly", 54900, 50000000),
        ("gpt-6-astra", "daily", 39000, 0),
        ("gpt-6-astra", "weekly", 64900, 50000000),
    ],
)
@pytest.mark.parametrize("promo", [True, False])
def test_fixed_packages_keep_main_quota_separate_from_shared_bonus(
    model: str, plan: str, price: int, bonus: int, promo: bool
) -> None:
    result = quote(model, plan, None, promo)
    assert result["price_idr"] == result["regular_idr"] == price
    assert result["included_tokens"] == 50_000_000
    assert result["bonus_tokens"] == bonus
    assert result["bonus_pool"] == ("shared" if bonus else None)
    assert result["bonus_models"] == (["gpt-5.6-luna", "deepseek-v4.1-flash"] if bonus else [])
    assert result["method"] == "fixed-model-package"
    assert result["effective_idr_per_million"] == str(Decimal(price) / 50)
    assert quote(model, plan, 50_000_000, promo)["packs"] == 1
    overflow = quote(model, plan, 50_000_001, promo)
    assert overflow["packs"] == 2
    assert overflow["total_idr"] == price * 2
    assert quote(model, plan, 100_000_000, promo)["packs"] == 2
    assert result["checkout_enabled"] is False
