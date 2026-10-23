"""Retail-only quotes: decimal rounding, public privacy, concurrency and validation."""

import asyncio
from decimal import Decimal

import pytest

from app.public import quote, rounded_price
from tests.conftest import ClientFactory


@pytest.mark.parametrize(
    ("plan", "price", "tokens"),
    [
        ("daily", 9900, 100_000_000),
        ("weekly", 34900, 250_000_000),
        ("monthly", 49900, 500_000_000),
    ],
)
def test_owner_prices_and_zero_multiplier_floor(plan: str, price: int, tokens: int) -> None:
    result = quote("deepseek-v4.1-flash", plan, None)
    assert result["price_idr"] == price
    assert result["included_tokens"] == tokens
    assert result["packs"] == 1
    assert result["checkout_enabled"] is False
    assert quote("deepseek-v4.1-flash-sg", plan, None)["price_idr"] == price


def test_promo_rounding_and_full_package_boundaries() -> None:
    assert quote("deepseek-v4.1-flash", "monthly", None, False)["price_idr"] == 59900
    result = quote("glm-5.3-flash", "daily", 100_000_001)
    assert result["price_idr"] == 19800  # 0.06 / 0.03, not arbitrary currency conversion
    assert result["packs"] == 2
    assert result["total_idr"] == 39600
    assert quote("gpt-5.6-luna", "daily", 1)["price_idr"] == 46200
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
        assert len(body["models"]) == 17
        assert body["version"] == "2.173.0"
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
