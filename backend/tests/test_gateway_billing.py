"""Token accounting, Rupiah cost, and balance debits (FR-3.18 to FR-3.23, FR-5.1)."""

import asyncio
import json
from decimal import Decimal

import pytest

from app.gateway.usage import Prices, Usage, compute_cost_idr
from tests.conftest import ClientFactory
from tests.gateway_support import anthropic_body, auth, gateway_data, openai_body, setting

# Rupiah per 1M tokens: input, output, cache write, cache read.
PRICES = ("3000", "15000", "3750", "300")


def test_cost_rounds_up_to_whole_rupiah() -> None:
    prices = Prices(Decimal(3000), Decimal(15000), Decimal(3750), Decimal(300))
    # 11*3000 + 7*15000 = 138_000 -> 0.138 Rp -> rounds up to 1.
    assert compute_cost_idr(Usage(input_tokens=11, output_tokens=7), prices) == 1
    # Exactly 1_000_000 * 3000 / 1M = 3000, no rounding.
    assert compute_cost_idr(Usage(input_tokens=1_000_000), prices) == 3000
    # 1_000_001 input tokens -> 3000.003 -> 3001.
    assert compute_cost_idr(Usage(input_tokens=1_000_001), prices) == 3001
    assert compute_cost_idr(Usage(), prices) == 0


def test_cost_keeps_fractional_prices_exact() -> None:
    prices = Prices(Decimal("0.01"), Decimal(0), Decimal(0), Decimal(0))
    assert compute_cost_idr(Usage(input_tokens=100_000_000), prices) == 1
    assert compute_cost_idr(Usage(input_tokens=100_000_001), prices) == 2


def _read_sse_payloads(text: str) -> list[dict[str, object]]:
    payloads = []
    for line in text.splitlines():
        if line.startswith("data:") and line[5:].strip() != "[DONE]":
            payloads.append(json.loads(line[5:]))
    return payloads


@pytest.mark.parametrize(
    ("endpoint", "stream"),
    [
        ("/v1/chat/completions", False),
        ("/v1/chat/completions", True),
        ("/v1/messages", False),
        ("/v1/messages", True),
    ],
)
async def test_usage_and_cost_recorded_for_each_format(
    gateway_factory: ClientFactory, endpoint: str, stream: bool
) -> None:
    async with gateway_data() as data:
        member = await data.member(balance=50_000)
        # 1.2M input + 0.4M output tokens: 3600 + 6000 = Rp 9.600 exactly.
        model = await data.model("ok?prompt=1200000&completion=400000", prices=PRICES)
        body_fn = openai_body if endpoint.endswith("completions") else anthropic_body
        async with gateway_factory() as client:
            response = await client.post(
                endpoint, json=body_fn(model, stream=stream), headers=auth(member.key)
            )
        assert response.status_code == 200
        request_id = response.headers["x-request-id"]

        rows = await data.fetch(
            "SELECT input_tokens, output_tokens, cache_write_tokens, cache_read_tokens,"
            " usage_estimated, cost_idr, status_code, is_stream, price_snapshot, endpoint,"
            " model_public_name FROM requests WHERE request_id = :rid",
            rid=request_id,
        )
        assert len(rows) == 1
        row = rows[0]
        assert (row.input_tokens, row.output_tokens) == (1_200_000, 400_000)
        assert (row.cache_write_tokens, row.cache_read_tokens) == (0, 0)
        assert row.usage_estimated is False
        assert row.cost_idr == 9_600
        assert row.status_code == 200
        assert row.is_stream is stream
        assert row.endpoint == endpoint
        assert row.model_public_name == model
        assert row.price_snapshot == {
            "input_per_m": "3000.00",
            "output_per_m": "15000.00",
            "cache_write_per_m": "3750.00",
            "cache_read_per_m": "300.00",
        }

        balance = await data.scalar(
            "SELECT balance_idr FROM users WHERE id = :id", id=member.user_id
        )
        assert balance == 50_000 - 9_600
        ledger = await data.fetch(
            "SELECT type, amount_idr, balance_after_idr FROM ledger_entries"
            " WHERE request_id = :rid",
            rid=request_id,
        )
        assert [(e.type, e.amount_idr, e.balance_after_idr) for e in ledger] == [
            ("usage", -9_600, 40_400)
        ]
        # Balance column always equals the ledger sum (FR-5.1).
        ledger_sum = await data.scalar(
            "SELECT sum(amount_idr) FROM ledger_entries WHERE user_id = :id", id=member.user_id
        )
        assert ledger_sum == balance


@pytest.mark.parametrize("stream", [False, True])
async def test_anthropic_cache_write_and_read_billed_separately(
    gateway_factory: ClientFactory, stream: bool
) -> None:
    async with gateway_data() as data:
        member = await data.member(balance=50_000)
        model = await data.model(
            "ok?prompt=1000&completion=1000&cache_write=1000000&cache_read=2000000",
            prices=PRICES,
        )
        async with gateway_factory() as client:
            response = await client.post(
                "/v1/messages", json=anthropic_body(model, stream=stream), headers=auth(member.key)
            )
        assert response.status_code == 200
        row = (
            await data.fetch(
                "SELECT input_tokens, output_tokens, cache_write_tokens, cache_read_tokens,"
                " cost_idr FROM requests WHERE request_id = :rid",
                rid=response.headers["x-request-id"],
            )
        )[0]
        assert (row.input_tokens, row.output_tokens) == (1000, 1000)
        assert (row.cache_write_tokens, row.cache_read_tokens) == (1_000_000, 2_000_000)
        # 1000*3000 + 1000*15000 + 1M*3750 + 2M*300 = 3M + 15M + 3.75B + 600M = 4.368B / 1M
        assert row.cost_idr == 4_368


@pytest.mark.parametrize("stream", [False, True])
async def test_openai_cached_tokens_split_from_prompt(
    gateway_factory: ClientFactory, stream: bool
) -> None:
    async with gateway_data() as data:
        member = await data.member(balance=50_000)
        model = await data.model("ok?prompt=1000000&completion=0&cached=600000", prices=PRICES)
        async with gateway_factory() as client:
            response = await client.post(
                "/v1/chat/completions",
                json=openai_body(model, stream=stream),
                headers=auth(member.key),
            )
        assert response.status_code == 200
        row = (
            await data.fetch(
                "SELECT input_tokens, cache_read_tokens, cost_idr FROM requests"
                " WHERE request_id = :rid",
                rid=response.headers["x-request-id"],
            )
        )[0]
        # prompt_tokens includes cached tokens: 400k billed as input, 600k as cache read.
        assert (row.input_tokens, row.cache_read_tokens) == (400_000, 600_000)
        assert row.cost_idr == 1200 + 180


@pytest.mark.parametrize(
    ("endpoint", "stream"),
    [
        ("/v1/chat/completions", False),
        ("/v1/chat/completions", True),
        ("/v1/messages", False),
        ("/v1/messages", True),
    ],
)
async def test_missing_usage_is_estimated(
    gateway_factory: ClientFactory, endpoint: str, stream: bool
) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model("ok?nousage=1&chunks=8")
        body_fn = openai_body if endpoint.endswith("completions") else anthropic_body
        async with gateway_factory() as client:
            response = await client.post(
                endpoint, json=body_fn(model, stream=stream), headers=auth(member.key)
            )
        assert response.status_code == 200
        row = (
            await data.fetch(
                "SELECT input_tokens, output_tokens, usage_estimated FROM requests"
                " WHERE request_id = :rid",
                rid=response.headers["x-request-id"],
            )
        )[0]
        assert row.usage_estimated is True
        assert row.input_tokens > 0
        assert row.output_tokens > 0


async def test_price_zero_records_tokens_without_ledger_entry(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        member = await data.member(balance=5_000)
        model = await data.model("ok?prompt=500&completion=100")
        async with gateway_factory() as client:
            response = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
        assert response.status_code == 200
        rid = response.headers["x-request-id"]
        row = (
            await data.fetch(
                "SELECT input_tokens, output_tokens, cost_idr FROM requests"
                " WHERE request_id = :rid",
                rid=rid,
            )
        )[0]
        assert (row.input_tokens, row.output_tokens, row.cost_idr) == (500, 100, 0)
        assert (
            await data.scalar(
                "SELECT count(*) FROM ledger_entries WHERE request_id = :rid", rid=rid
            )
            == 0
        )
        assert (
            await data.scalar("SELECT balance_idr FROM users WHERE id = :id", id=member.user_id)
            == 5_000
        )


async def test_twenty_parallel_requests_debit_balance_exactly(
    gateway_factory: ClientFactory,
) -> None:
    """FR-3.21 / R12: row lock keeps parallel debits from overwriting each other."""
    async with gateway_data() as data:
        member = await data.member(balance=1_000_000)
        # 1M input tokens at Rp 3.000 per 1M plus 100k output at Rp 15.000 per 1M = Rp 4.500.
        model = await data.model("ok?prompt=1000000&completion=100000&ttft=0.05", prices=PRICES)
        # Half of the requests stream; lift the default limit of 8 concurrent streams.
        async with (
            setting(data, "max_concurrent_streams_per_user", 20),
            gateway_factory() as client,
        ):

            async def one(i: int) -> int:
                stream = i % 2 == 0
                endpoint = "/v1/chat/completions" if i % 4 < 2 else "/v1/messages"
                body_fn = openai_body if endpoint.endswith("completions") else anthropic_body
                response = await client.post(
                    endpoint, json=body_fn(model, stream=stream), headers=auth(member.key)
                )
                return response.status_code

            statuses = await asyncio.gather(*(one(i) for i in range(20)))
        assert statuses == [200] * 20

        balance = await data.scalar(
            "SELECT balance_idr FROM users WHERE id = :id", id=member.user_id
        )
        assert balance == 1_000_000 - 20 * 4_500
        entries = await data.fetch(
            "SELECT amount_idr, balance_after_idr FROM ledger_entries"
            " WHERE user_id = :id AND type = 'usage' ORDER BY balance_after_idr DESC",
            id=member.user_id,
        )
        assert len(entries) == 20
        assert all(e.amount_idr == -4_500 for e in entries)
        # Each debit saw the previous one: balances step down by exactly one cost each.
        assert [e.balance_after_idr for e in entries] == [
            1_000_000 - 4_500 * (i + 1) for i in range(20)
        ]
        assert (
            await data.scalar(
                "SELECT count(*) FROM requests WHERE user_id = :id AND cost_idr = 4500",
                id=member.user_id,
            )
            == 20
        )


async def test_balance_may_go_slightly_negative_then_blocks(
    gateway_factory: ClientFactory,
) -> None:
    """FR-3.23: the last request that passed the minimum check may overdraw; the next gets 402."""
    async with gateway_data() as data:
        member = await data.member(balance=1_500)
        model = await data.model("ok?prompt=1000000&completion=0", prices=PRICES)
        async with gateway_factory() as client:
            first = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
            second = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
        assert first.status_code == 200
        assert second.status_code == 402
        assert (
            await data.scalar("SELECT balance_idr FROM users WHERE id = :id", id=member.user_id)
            == 1_500 - 3_000
        )
