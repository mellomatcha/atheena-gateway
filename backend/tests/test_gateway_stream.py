"""Forwarding, streaming, heartbeats, upstream errors, disconnects, and privacy (FR-3.11 to 3.17,
FR-3.19, FR-3.22, FR-4.0, PRD §4.3.4)."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.main import create_app
from tests.conftest import FAST_HEARTBEATS, ClientFactory, make_settings
from tests.fake_upstream.app import RECEIVED, RESPONSE_TEXT
from tests.fake_upstream.server import serve
from tests.gateway_support import anthropic_body, auth, gateway_data, openai_body

BodyFn = Callable[..., dict[str, Any]]
ENDPOINTS = [("/v1/chat/completions", openai_body), ("/v1/messages", anthropic_body)]
PROMPT_MARKER = "SECRET-PROMPT-TEXT"
RESPONSE_MARKER = "SECRET-RESPONSE-TEXT"


def assert_no_upstream_leak(response: httpx.Response) -> None:
    """Upstream ids, provider names, and upstream error text never reach the client."""
    for needle in ("fake/", "fakeprovider", "codebuddy", "secret-upstream-model"):
        assert needle not in response.text
        assert all(needle not in value for value in response.headers.values())


def sse_payloads(text: str) -> list[dict[str, Any]]:
    return [
        json.loads(line[5:])
        for line in text.splitlines()
        if line.startswith("data:") and line[5:].strip() != "[DONE]"
    ]


async def _last_received() -> dict[str, Any]:
    return RECEIVED[-1]


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
@pytest.mark.parametrize("stream", [False, True])
async def test_model_translated_and_rewritten_back(
    gateway_factory: ClientFactory, endpoint: str, body_fn: BodyFn, stream: bool
) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model("ok?chunks=4")
        async with gateway_factory() as client:
            response = await client.post(
                endpoint, json=body_fn(model, stream=stream), headers=auth(member.key)
            )
    assert response.status_code == 200
    received = await _last_received()
    assert received["body"]["model"] == "fake/ok?chunks=4"  # FR-3.11
    assert_no_upstream_leak(response)
    if stream:
        assert response.headers["content-type"].startswith("text/event-stream")
        payloads = sse_payloads(response.text)
        models = [p.get("model") or (p.get("message") or {}).get("model") for p in payloads]
        assert model in models
        assert set(filter(None, models)) == {model}
    else:
        body = response.json()
        assert body["model"] == model
        assert RESPONSE_TEXT in response.text


async def test_openai_stream_injects_include_usage(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model()
        async with gateway_factory() as client:
            response = await client.post(
                "/v1/chat/completions",
                json=openai_body(model, stream=True, stream_options={"foo": "bar"}),
                headers=auth(member.key),
            )
    assert response.status_code == 200
    forwarded = (await _last_received())["body"]
    assert forwarded["stream_options"] == {"foo": "bar", "include_usage": True}  # FR-3.13
    # The usage chunk is forwarded to the client too.
    assert any("usage" in p for p in sse_payloads(response.text))


async def test_internal_headers_and_portal_key_not_forwarded(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model()
        async with gateway_factory() as client:
            response = await client.post(
                "/v1/messages",
                json=anthropic_body(
                    model,
                    system=[
                        {"type": "text", "text": "ctx", "cache_control": {"type": "ephemeral"}}
                    ],
                ),
                headers={
                    "x-api-key": member.key,
                    "X-Project": "riset",
                    "anthropic-version": "2023-06-01",
                    "anthropic-beta": "prompt-caching-2024-07-31",
                    "X-Custom-Header": "should-not-pass",
                },
            )
    assert response.status_code == 200
    received = await _last_received()
    headers = received["headers"]
    assert headers["authorization"] == "Bearer fake-upstream-key"  # FR-3.16
    assert member.key not in json.dumps(headers)
    assert "x-api-key" not in headers
    assert "x-project" not in headers
    assert "x-custom-header" not in headers
    assert headers["anthropic-version"] == "2023-06-01"
    assert headers["anthropic-beta"] == "prompt-caching-2024-07-31"
    # FR-3.12: Anthropic body passed natively, cache_control intact.
    assert received["path"] == "/v1/messages"
    assert received["body"]["system"][0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
async def test_stream_heartbeat_before_first_byte(
    gateway_factory: ClientFactory, endpoint: str, body_fn: BodyFn
) -> None:
    """FR-3.15: `: ping` every interval (0.2 s in tests) until the upstream sends a byte."""
    async with gateway_data() as data:
        member = await data.member()
        slow_headers = await data.model("ok?delay=0.7")
        slow_body = await data.model("ok?ttft=0.7")
        async with gateway_factory() as client:
            for model in (slow_headers, slow_body):
                response = await client.post(
                    endpoint, json=body_fn(model, stream=True), headers=auth(member.key)
                )
                assert response.status_code == 200
                text = response.text
                first_data = text.index("data:")
                assert text[:first_data].count(": ping\n\n") >= 2
                # Heartbeats stop once data flows.
                assert ": ping" not in text[first_data:]
                assert_no_upstream_leak(response)
                ttft = await data.scalar(
                    "SELECT ttft_ms FROM requests WHERE request_id = :rid",
                    rid=response.headers["x-request-id"],
                )
                assert ttft >= 600


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
async def test_nonstream_heartbeat_is_leading_whitespace(
    gateway_factory: ClientFactory, endpoint: str, body_fn: BodyFn
) -> None:
    """Non-stream: after the delay (0.3 s), a space every interval; the JSON stays valid."""
    async with gateway_data() as data:
        member = await data.member()
        slow = await data.model("ok?delay=1.0&prompt=5&completion=3")
        fast = await data.model("ok?prompt=5&completion=3")
        async with gateway_factory() as client:
            slow_response = await client.post(
                endpoint, json=body_fn(slow), headers=auth(member.key)
            )
            fast_response = await client.post(
                endpoint, json=body_fn(fast), headers=auth(member.key)
            )
    assert slow_response.status_code == 200
    raw = slow_response.content
    assert raw.startswith(b"  ")
    assert json.loads(raw)["model"] == slow  # leading whitespace is valid JSON
    assert fast_response.content.startswith(b"{")
    assert_no_upstream_leak(slow_response)


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
@pytest.mark.parametrize(
    ("upstream_status", "expected"), [(400, 400), (429, 429), (500, 502), (503, 502)]
)
async def test_upstream_error_before_commit_keeps_status(
    gateway_factory: ClientFactory,
    endpoint: str,
    body_fn: BodyFn,
    upstream_status: int,
    expected: int,
) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model(f"ok?status={upstream_status}", prices=("5000", "0", "0", "0"))
        async with gateway_factory() as client:
            for stream in (False, True):
                response = await client.post(
                    endpoint, json=body_fn(model, stream=stream), headers=auth(member.key)
                )
                assert response.status_code == expected
                assert_no_upstream_leak(response)
                body = response.json()
                assert ("type" in body) is (endpoint == "/v1/messages")
                row = (
                    await data.fetch(
                        "SELECT status_code, error_type, cost_idr, input_tokens FROM requests"
                        " WHERE request_id = :rid",
                        rid=response.headers["x-request-id"],
                    )
                )[0]
                # FR-3.22: failed at the upstream, no usage reported, nothing billed.
                assert (row.status_code, row.cost_idr, row.input_tokens) == (expected, 0, 0)
                assert row.error_type is not None


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
async def test_upstream_error_after_heartbeat_is_in_band(
    gateway_factory: ClientFactory, endpoint: str, body_fn: BodyFn
) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model("ok?status=500&delay=0.8")
        async with gateway_factory() as client:
            stream = await client.post(
                endpoint, json=body_fn(model, stream=True), headers=auth(member.key)
            )
            nonstream = await client.post(endpoint, json=body_fn(model), headers=auth(member.key))
    # 200 was already committed by the heartbeat, so the error travels in the body.
    assert stream.status_code == 200
    assert ": ping" in stream.text
    errors = [p for p in sse_payloads(stream.text) if "error" in p]
    assert len(errors) == 1
    if endpoint == "/v1/messages":
        assert "event: error" in stream.text
    assert nonstream.status_code == 200
    assert nonstream.content.startswith(b" ")
    assert "error" in json.loads(nonstream.content)
    assert_no_upstream_leak(stream)
    assert_no_upstream_leak(nonstream)


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
async def test_inband_upstream_error_is_sanitized(
    gateway_factory: ClientFactory, endpoint: str, body_fn: BodyFn
) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model("ok?chunks=5&inband_error=2")
        async with gateway_factory() as client:
            response = await client.post(
                endpoint, json=body_fn(model, stream=True), headers=auth(member.key)
            )
        assert response.status_code == 200
        assert_no_upstream_leak(response)
        payloads = sse_payloads(response.text)
        assert "error" in payloads[-1]
        row = (
            await data.fetch(
                "SELECT status_code, error_type, usage_estimated, output_tokens FROM requests"
                " WHERE request_id = :rid",
                rid=response.headers["x-request-id"],
            )
        )[0]
        assert row.status_code == 502
        assert row.error_type == "upstream_error"
        # Two chunks were delivered before the error; they are estimated, not dropped.
        assert row.usage_estimated is True
        assert row.output_tokens > 0


async def test_upstream_cut_mid_stream_records_partial_usage(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model("ok?chunks=6&cut=3")
        async with gateway_factory() as client:
            response = await client.post(
                "/v1/messages", json=anthropic_body(model, stream=True), headers=auth(member.key)
            )
        assert response.status_code == 200
        assert_no_upstream_leak(response)
        row = (
            await data.fetch(
                "SELECT input_tokens, output_tokens, usage_estimated, error_type FROM requests"
                " WHERE request_id = :rid",
                rid=response.headers["x-request-id"],
            )
        )[0]
        # message_start reported input tokens; output is estimated from the delivered text.
        assert row.input_tokens == 11
        assert row.output_tokens > 0
        assert row.usage_estimated is True


async def test_upstream_unreachable_is_502(client_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model()
        async with client_factory(
            upstream_base_url="http://127.0.0.1:9/v1", **FAST_HEARTBEATS
        ) as client:
            response = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "upstream_unreachable"
    assert "127.0.0.1" not in response.text


async def test_client_disconnect_mid_stream_still_records_usage(fake_upstream_url: str) -> None:
    """A client that hangs up mid-stream is still billed for what it received."""
    async with gateway_data() as data:
        member = await data.member(balance=100_000)
        model = await data.model(
            "ok?chunks=3&hang=1&prompt=1000000", prices=("5000", "0", "0", "0")
        )
        app = create_app(make_settings(upstream_base_url=fake_upstream_url, **FAST_HEARTBEATS))
        with serve(app) as base:
            async with (
                httpx.AsyncClient(base_url=base, timeout=10) as client,
                client.stream(
                    "POST",
                    "/v1/messages",
                    json=anthropic_body(model, stream=True),
                    headers=auth(member.key),
                ) as response,
            ):
                request_id = response.headers["x-request-id"]
                async for chunk in response.aiter_bytes():
                    if b"content_block_delta" in chunk:
                        break
            row = None
            for _ in range(100):
                rows = await data.fetch(
                    "SELECT status_code, error_type, input_tokens, output_tokens,"
                    " usage_estimated, cost_idr FROM requests WHERE request_id = :rid",
                    rid=request_id,
                )
                if rows:
                    row = rows[0]
                    break
                await asyncio.sleep(0.05)
        assert row is not None
        assert (row.status_code, row.error_type) == (499, "client_disconnected")
        assert row.input_tokens == 1_000_000
        assert row.output_tokens > 0
        assert row.usage_estimated is True
        assert row.cost_idr == 5_000
        balance = await data.scalar(
            "SELECT balance_idr FROM users WHERE id = :id", id=member.user_id
        )
        assert balance == 95_000
        # The stream slot was released.
        from redis.asyncio import Redis

        from tests.conftest import TEST_REDIS_URL

        redis = Redis.from_url(TEST_REDIS_URL)
        try:
            assert await redis.zcard(f"streams:{member.user_id}") == 0
        finally:
            await redis.aclose()


async def test_request_id_header_matches_record(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model()
        async with gateway_factory() as client:
            response = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
        request_id = response.headers["x-request-id"]
        assert (
            await data.scalar(
                "SELECT count(*) FROM requests WHERE request_id = :rid", rid=request_id
            )
            == 1
        )


async def test_prompt_and_response_never_logged(
    gateway_factory: ClientFactory, capsys: pytest.CaptureFixture[str]
) -> None:
    """PRD §4.3.4: logs carry metadata only, including on errors."""
    async with gateway_data() as data:
        member = await data.member()
        scenarios = ["ok?chunks=4", "ok?status=500", "ok?chunks=5&inband_error=2", "ok?nousage=1"]
        models = [await data.model(s) for s in scenarios]
        async with gateway_factory() as client:
            for model in models:
                for endpoint, body_fn in ENDPOINTS:
                    for stream in (False, True):
                        await client.post(
                            endpoint, json=body_fn(model, stream=stream), headers=auth(member.key)
                        )
            await client.post("/v1/chat/completions", json=openai_body(models[0]))
    out = capsys.readouterr().out
    assert "proxy request" in out
    for needle in (PROMPT_MARKER, RESPONSE_MARKER, member.key, "fake-upstream-key"):
        assert needle not in out
