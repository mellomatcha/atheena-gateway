"""Pre-upstream checks (FR-3.1 to FR-3.10), error formats (FR-3.24), and key caching (FR-3.2)."""

from collections.abc import Callable
from typing import Any

import pytest
from redis.asyncio import Redis

from app.gateway.keys import hash_key, invalidate_keys, resolve_key
from tests.conftest import TEST_REDIS_URL, ClientFactory
from tests.gateway_support import anthropic_body, auth, gateway_data, openai_body, setting

BodyFn = Callable[..., dict[str, Any]]

ENDPOINTS = [
    ("/v1/chat/completions", openai_body),
    ("/v1/messages", anthropic_body),
]


def assert_error_format(endpoint: str, body: dict[str, object], expected_type: str) -> str:
    """Check the endpoint-specific error envelope and return the message."""
    if endpoint == "/v1/messages":
        assert body["type"] == "error"
        error = body["error"]
        assert isinstance(error, dict)
        assert error["type"] == expected_type
        return str(error["message"])
    error = body["error"]
    assert isinstance(error, dict)
    assert set(error) == {"message", "type", "param", "code"}
    return str(error["message"])


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
async def test_missing_or_unknown_key_is_401(
    gateway_factory: ClientFactory, endpoint: str, body_fn: BodyFn
) -> None:
    async with gateway_data() as data:
        model = await data.model()
        async with gateway_factory() as client:
            missing = await client.post(endpoint, json=body_fn(model))
            unknown = await client.post(
                endpoint,
                json=body_fn(model),
                headers=auth("sk-ath-" + "x" * 40),
            )
            malformed = await client.post(
                endpoint,
                json=body_fn(model),
                headers=auth("not-a-key"),
            )
    for response in (missing, unknown, malformed):
        assert response.status_code == 401
        assert_error_format(endpoint, response.json(), "authentication_error")


async def test_x_api_key_header_is_accepted(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model()
        async with gateway_factory() as client:
            response = await client.post(
                "/v1/messages", json=anthropic_body(model), headers={"x-api-key": member.key}
            )
    assert response.status_code == 200


async def test_revoked_key_and_suspended_user_are_401(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        revoked = await data.member()
        suspended = await data.member()
        model = await data.model()
        await data.execute(
            "UPDATE api_keys SET status = 'revoked', revoked_at = now() WHERE id = :id",
            id=revoked.api_key_id,
        )
        await data.execute(
            "UPDATE users SET status = 'suspended' WHERE id = :id", id=suspended.user_id
        )
        async with gateway_factory() as client:
            for member in (revoked, suspended):
                response = await client.post(
                    "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
                )
                assert response.status_code == 401


async def test_key_cache_serves_for_60s_until_invalidated() -> None:
    """FR-3.2 / FR-2.4: identity is cached in Redis; invalidation makes a revoke instant."""
    redis = Redis.from_url(TEST_REDIS_URL)
    try:
        async with gateway_data() as data:
            member = await data.member()
            from sqlalchemy.ext.asyncio import AsyncSession

            async with AsyncSession(data.engine) as session:
                first = await resolve_key(redis, session, member.key)
                assert first is not None
                ttl = await redis.ttl(f"apikey:{hash_key(member.key)}")
                assert 0 < ttl <= 60

                await data.execute(
                    "UPDATE api_keys SET status = 'revoked' WHERE id = :id", id=member.api_key_id
                )
                # Still cached: the revoke only applies once the cache entry is dropped.
                assert await resolve_key(redis, session, member.key) is not None
                await invalidate_keys(redis, [hash_key(member.key)])
                assert await resolve_key(redis, session, member.key) is None
    finally:
        await redis.aclose()


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
async def test_balance_below_minimum_is_402(
    gateway_factory: ClientFactory, endpoint: str, body_fn: BodyFn
) -> None:
    async with gateway_data() as data:
        member = await data.member(balance=999)
        model = await data.model()
        async with gateway_factory() as client:
            response = await client.post(
                endpoint,
                json=body_fn(model),
                headers=auth(member.key),
            )
    assert response.status_code == 402
    message = assert_error_format(endpoint, response.json(), "billing_error")
    assert message == "Saldo habis, silakan top-up."


async def test_minimum_balance_follows_setting(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member(balance=4_000)
        model = await data.model()
        async with setting(data, "min_balance_idr", 5_000), gateway_factory() as client:
            response = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
    assert response.status_code == 402


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
async def test_model_above_tier_is_403_with_allowed_list(
    gateway_factory: ClientFactory, endpoint: str, body_fn: BodyFn
) -> None:
    async with gateway_data() as data:
        member = await data.member(tier="basic")
        allowed = await data.model(min_tier="basic")
        opus = await data.model(min_tier="advanced")
        async with gateway_factory() as client:
            response = await client.post(
                endpoint,
                json=body_fn(opus),
                headers=auth(member.key),
            )
    assert response.status_code == 403
    message = assert_error_format(endpoint, response.json(), "permission_error")
    assert allowed in message
    assert opus in message  # the requested name is echoed back
    assert f", {opus}" not in message and f": {opus}" not in message  # but not listed as allowed


async def test_advanced_tier_may_use_advanced_models(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member(tier="advanced")
        opus = await data.model(min_tier="advanced")
        async with gateway_factory() as client:
            response = await client.post(
                "/v1/chat/completions", json=openai_body(opus), headers=auth(member.key)
            )
    assert response.status_code == 200


async def test_unknown_and_inactive_models_are_403(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member()
        inactive = await data.model(is_active=False)
        async with gateway_factory() as client:
            for name in (inactive, "no-such-model"):
                response = await client.post(
                    "/v1/chat/completions", json=openai_body(name), headers=auth(member.key)
                )
                assert response.status_code == 403


async def test_key_allowlist_narrows_models(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user_id = await data.user()
        first = await data.model()
        second = await data.model()
        key, _ = await data.key(user_id, allowlist=[first])
        async with gateway_factory() as client:
            ok = await client.post(
                "/v1/chat/completions", json=openai_body(first), headers=auth(key)
            )
            denied = await client.post(
                "/v1/chat/completions", json=openai_body(second), headers=auth(key)
            )
            listed = await client.get("/v1/models", headers=auth(key))
    assert ok.status_code == 200
    assert denied.status_code == 403
    assert [m["id"] for m in listed.json()["data"]] == [first]


async def test_endpoint_format_must_match_model(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member()
        openai_only = await data.model(api_format="openai")
        async with gateway_factory() as client:
            response = await client.post(
                "/v1/messages", json=anthropic_body(openai_only), headers=auth(member.key)
            )
    assert response.status_code == 400
    assert_error_format("/v1/messages", response.json(), "invalid_request_error")


async def test_daily_cap_per_user_and_key_is_429(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        capped_user = await data.member(daily_cap=4_000)
        user_id = await data.user()
        capped_key, _ = await data.key(user_id, daily_cap=4_000)
        model = await data.model("ok?prompt=1000000&completion=0", prices=("5000", "0", "0", "0"))
        async with gateway_factory() as client:
            for key in (capped_user.key, capped_key):
                first = await client.post(
                    "/v1/chat/completions", json=openai_body(model), headers=auth(key)
                )
                second = await client.post(
                    "/v1/chat/completions", json=openai_body(model), headers=auth(key)
                )
                assert first.status_code == 200
                assert second.status_code == 429
                assert second.json()["error"]["code"] == "daily_cap_exceeded"
                assert int(second.headers["retry-after"]) > 0


async def test_default_user_daily_cap_setting_applies(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model("ok?prompt=1000000&completion=0", prices=("5000", "0", "0", "0"))
        async with setting(data, "default_user_daily_cap_idr", 1_000), gateway_factory() as client:
            first = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
            second = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
    assert (first.status_code, second.status_code) == (200, 429)


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
async def test_rate_limit_per_key_is_429_with_retry_after(
    gateway_factory: ClientFactory, endpoint: str, body_fn: BodyFn
) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model()
        async with setting(data, "rate_limit_per_key_per_minute", 3), gateway_factory() as client:
            statuses = []
            for _ in range(4):
                response = await client.post(
                    endpoint,
                    json=body_fn(model),
                    headers=auth(member.key),
                )
                statuses.append(response.status_code)
    assert statuses == [200, 200, 200, 429]
    assert 1 <= int(response.headers["retry-after"]) <= 60
    assert_error_format(endpoint, response.json(), "rate_limit_error")


async def test_rate_limit_per_user_spans_keys(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user_id = await data.user()
        key_a, _ = await data.key(user_id)
        key_b, _ = await data.key(user_id)
        model = await data.model()
        async with setting(data, "rate_limit_per_user_per_minute", 2), gateway_factory() as client:
            statuses = [
                (
                    await client.post(
                        "/v1/chat/completions", json=openai_body(model), headers=auth(key)
                    )
                ).status_code
                for key in (key_a, key_b, key_a)
            ]
    assert statuses == [200, 200, 429]


async def test_concurrent_stream_limit_is_429(gateway_factory: ClientFactory) -> None:
    import asyncio

    async with gateway_data() as data:
        member = await data.member()
        slow = await data.model("ok?ttft=0.5")
        async with (
            setting(data, "max_concurrent_streams_per_user", 2),
            gateway_factory() as client,
        ):
            responses = await asyncio.gather(
                *(
                    client.post(
                        "/v1/chat/completions",
                        json=openai_body(slow, stream=True),
                        headers=auth(member.key),
                    )
                    for _ in range(3)
                )
            )
            statuses = sorted(r.status_code for r in responses)
            # Slots are released when streams finish.
            after = await client.post(
                "/v1/chat/completions",
                json=openai_body(slow, stream=True),
                headers=auth(member.key),
            )
    assert statuses == [200, 200, 429]
    assert after.status_code == 200


async def test_body_over_limit_is_413(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member()
        model = await data.model()
        big = openai_body(model, padding="x" * 2_000)
        async with setting(data, "max_body_bytes", 1_024), gateway_factory() as client:
            response = await client.post("/v1/chat/completions", json=big, headers=auth(member.key))
            anthropic = await client.post(
                "/v1/messages",
                json=anthropic_body(model, padding="x" * 2_000),
                headers=auth(member.key),
            )
    assert response.status_code == 413
    assert anthropic.status_code == 413
    assert_error_format("/v1/messages", anthropic.json(), "request_too_large")


async def test_invalid_json_and_missing_model_are_400(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member()
        async with gateway_factory() as client:
            invalid = await client.post(
                "/v1/chat/completions",
                content=b"not json",
                headers={**auth(member.key), "content-type": "application/json"},
            )
            missing = await client.post(
                "/v1/chat/completions", json={"messages": []}, headers=auth(member.key)
            )
    assert invalid.status_code == 400
    assert missing.status_code == 400


@pytest.mark.parametrize(("endpoint", "body_fn"), ENDPOINTS)
async def test_official_only_project_rejects_experimental_models(
    gateway_factory: ClientFactory, endpoint: str, body_fn: BodyFn
) -> None:
    async with gateway_data() as data:
        await data.project("helios", official_only=True)
        member = await data.member()
        experimental = await data.model(category="experimental")
        official = await data.model(category="official")
        async with gateway_factory() as client:
            denied = await client.post(
                endpoint,
                json=body_fn(experimental),
                headers={**auth(member.key), "X-Project": "helios"},
            )
            allowed = await client.post(
                endpoint,
                json=body_fn(official),
                headers={**auth(member.key), "X-Project": "Helios"},
            )
            other_project = await client.post(
                endpoint,
                json=body_fn(experimental),
                headers={**auth(member.key), "X-Project": "riset"},
            )
        assert denied.status_code == 403
        assert_error_format(endpoint, denied.json(), "permission_error")
        assert allowed.status_code == 200
        assert other_project.status_code == 200
        projects = await data.fetch(
            "SELECT project FROM requests WHERE request_id IN (:a, :b)",
            a=allowed.headers["x-request-id"],
            b=other_project.headers["x-request-id"],
        )
        assert sorted(p.project for p in projects) == ["helios", "riset"]


async def test_rejected_requests_are_recorded_with_zero_cost(
    gateway_factory: ClientFactory,
) -> None:
    """FR-3.22: 401/402/403/413/429 are logged with cost 0 and no ledger entry."""
    async with gateway_data() as data:
        member = await data.member(balance=500)
        model = await data.model(prices=("5000", "0", "0", "0"))
        async with gateway_factory() as client:
            no_key = await client.post("/v1/chat/completions", json=openai_body(model))
            broke = await client.post(
                "/v1/chat/completions", json=openai_body(model), headers=auth(member.key)
            )
        rows = await data.fetch(
            "SELECT request_id::text AS rid, status_code, error_type, cost_idr, user_id"
            " FROM requests WHERE request_id IN (:a, :b)",
            a=no_key.headers["x-request-id"],
            b=broke.headers["x-request-id"],
        )
        by_id = {r.rid: r for r in rows}
        unauth = by_id[no_key.headers["x-request-id"]]
        assert (unauth.status_code, unauth.error_type, unauth.cost_idr) == (
            401,
            "invalid_api_key",
            0,
        )
        assert unauth.user_id is None
        low = by_id[broke.headers["x-request-id"]]
        assert (low.status_code, low.error_type, low.cost_idr) == (402, "insufficient_balance", 0)
        assert low.user_id == member.user_id
        assert (
            await data.scalar(
                "SELECT count(*) FROM ledger_entries WHERE user_id = :id AND type = 'usage'",
                id=member.user_id,
            )
            == 0
        )


async def test_models_list_filters_by_tier_and_activity(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        member = await data.member(tier="basic")
        basic = await data.model(min_tier="basic")
        advanced = await data.model(min_tier="advanced")
        inactive = await data.model(is_active=False)
        async with gateway_factory() as client:
            openai_list = await client.get("/v1/models", headers=auth(member.key))
            anthropic_list = await client.get(
                "/v1/models",
                headers={"x-api-key": member.key, "anthropic-version": "2023-06-01"},
            )
            unauth = await client.get("/v1/models")
    assert openai_list.status_code == 200
    ids = {m["id"] for m in openai_list.json()["data"]}
    assert basic in ids
    assert advanced not in ids and inactive not in ids
    assert all(m["owned_by"] == "atheena" for m in openai_list.json()["data"])
    assert anthropic_list.status_code == 200
    anthropic_ids = {m["id"] for m in anthropic_list.json()["data"]}
    assert anthropic_ids == ids
    assert all(m["type"] == "model" for m in anthropic_list.json()["data"])
    assert unauth.status_code == 401
    # Upstream ids and providers are never listed (FR-4.0).
    assert "fake/" not in openai_list.text and "fakeprovider" not in openai_list.text
    assert "fake/" not in anthropic_list.text
