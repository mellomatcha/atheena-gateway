"""Member key management and profile through the dashboard API (FR-2.x, §8)."""

import hashlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx

from app.gateway.keys import looks_like_key
from tests.conftest import ClientFactory
from tests.gateway_support import auth, gateway_data, openai_body, setting

CSRF = {"X-Atheena-CSRF": "1"}


def email_of(user_id: uuid.UUID) -> str:
    return f"u-{user_id}@example.test"


@asynccontextmanager
async def dashboard(
    gateway_factory: ClientFactory, user_id: uuid.UUID
) -> AsyncIterator[httpx.AsyncClient]:
    """A client acting as the given user via the development bypass."""
    async with gateway_factory(app_env="development", dev_auth_email=email_of(user_id)) as client:
        client.headers.update(CSRF)
        yield client


async def test_create_key_shows_it_once_and_stores_only_hash(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        user_id = await data.user()
        async with dashboard(gateway_factory, user_id) as client:
            created = await client.post("/app/api/keys", json={"name": "laptop-kantor"})
            listed = await client.get("/app/api/keys")
        assert created.status_code == 201
        body = created.json()
        key = body["key"]
        assert looks_like_key(key)  # sk-ath- + 40 base62 (FR-2.2)
        assert body["prefix"] == key[:12]
        assert body["name"] == "laptop-kantor"
        assert body["status"] == "active"
        # Listing never includes the plaintext key.
        assert "key" not in listed.json()[0]
        assert key not in listed.text
        row = (
            await data.fetch(
                "SELECT key_hash, key_prefix FROM api_keys WHERE id = :id", id=body["id"]
            )
        )[0]
        assert row.key_hash == hashlib.sha256(key.encode()).hexdigest()  # FR-2.3
        assert row.key_prefix == key[:12]


async def test_new_key_works_and_revoke_is_instant(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user_id = await data.user()
        async with dashboard(gateway_factory, user_id) as client:
            created = (await client.post("/app/api/keys", json={"name": "opencode"})).json()
            key = created["key"]
            before = await client.get("/v1/models", headers=auth(key))
            # Warm the Redis cache, then revoke: the next call must fail without waiting 60 s.
            await client.get("/v1/models", headers=auth(key))
            revoked = await client.delete(f"/app/api/keys/{created['id']}")
            after = await client.get("/v1/models", headers=auth(key))
    assert before.status_code == 200
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert revoked.json()["revoked_at"] is not None
    assert after.status_code == 401  # FR-2.4


async def test_active_key_limit(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user_id = await data.user()
        async with dashboard(gateway_factory, user_id) as client:
            ids = []
            for i in range(5):
                response = await client.post("/app/api/keys", json={"name": f"k{i}"})
                assert response.status_code == 201
                ids.append(response.json()["id"])
            sixth = await client.post("/app/api/keys", json={"name": "k5"})
            await client.delete(f"/app/api/keys/{ids[0]}")
            after_revoke = await client.post("/app/api/keys", json={"name": "k5"})
            async with setting(data, "max_active_keys_per_user", 6):
                with_setting = await client.post("/app/api/keys", json={"name": "k6"})
    assert sixth.status_code == 409
    assert sixth.json()["error"]["code"] == "key_limit"
    assert after_revoke.status_code == 201
    assert with_setting.status_code == 201


async def test_cannot_revoke_someone_elses_key(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        owner = await data.user()
        other = await data.user()
        _, key_id = await data.key(owner)
        async with dashboard(gateway_factory, other) as client:
            response = await client.delete(f"/app/api/keys/{key_id}")
            listed = await client.get("/app/api/keys")
        assert response.status_code == 404
        assert listed.json() == []
        status = await data.scalar("SELECT status FROM api_keys WHERE id = :id", id=key_id)
        assert status == "active"


async def test_key_list_shows_usage_totals(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user_id = await data.user()
        model = await data.model("ok?prompt=1000000&completion=0", prices=("2000", "0", "0", "0"))
        async with dashboard(gateway_factory, user_id) as client:
            created = (await client.post("/app/api/keys", json={"name": "k"})).json()
            for _ in range(2):
                await client.post(
                    "/v1/chat/completions", json=openai_body(model), headers=auth(created["key"])
                )
            listed = (await client.get("/app/api/keys")).json()
    entry = next(k for k in listed if k["id"] == created["id"])
    assert entry["usage"]["requests"] == 2
    assert entry["usage"]["input_tokens"] == 2_000_000
    assert entry["usage"]["cost_idr"] == 4_000
    assert entry["last_used_at"] is not None  # FR-2.6


async def test_key_allowlist_and_daily_cap(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user_id = await data.user(tier="basic")
        basic = await data.model(min_tier="basic")
        other = await data.model(min_tier="basic")
        advanced = await data.model(min_tier="advanced")
        async with dashboard(gateway_factory, user_id) as client:
            rejected = await client.post(
                "/app/api/keys", json={"name": "x", "model_allowlist": [advanced]}
            )
            created = await client.post(
                "/app/api/keys",
                json={"name": "narrow", "model_allowlist": [basic], "daily_cap_idr": 5_000},
            )
            key = created.json()["key"]
            models = await client.get("/v1/models", headers=auth(key))
            denied = await client.post(
                "/v1/chat/completions", json=openai_body(other), headers=auth(key)
            )
            bad_cap = await client.post("/app/api/keys", json={"name": "y", "daily_cap_idr": 0})
    assert rejected.status_code == 400
    assert rejected.json()["error"]["code"] == "invalid_allowlist"
    assert created.status_code == 201
    assert created.json()["model_allowlist"] == [basic]
    assert created.json()["daily_cap_idr"] == 5_000
    assert [m["id"] for m in models.json()["data"]] == [basic]
    assert denied.status_code == 403
    assert bad_cap.status_code == 422


async def test_patch_me_updates_profile(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user_id = await data.user()
        async with dashboard(gateway_factory, user_id) as client:
            response = await client.patch(
                "/app/api/me",
                json={
                    "display_name": "Dafin",
                    "low_balance_threshold_idr": 25_000,
                    "leaderboard_opt_out": True,
                },
            )
            invalid = await client.patch("/app/api/me", json={"display_name": ""})
            role_attempt = await client.patch("/app/api/me", json={"role": "admin"})
        assert response.status_code == 200
        body = response.json()
        assert body["display_name"] == "Dafin"
        assert body["low_balance_threshold_idr"] == 25_000
        assert body["leaderboard_opt_out"] is True
        assert invalid.status_code == 422
        # Unknown fields are ignored; the role cannot be self-assigned.
        assert role_attempt.status_code == 200
        assert role_attempt.json()["role"] == "member"
        role = await data.scalar("SELECT role FROM users WHERE id = :id", id=user_id)
        assert role == "member"


async def test_member_model_catalog_hides_upstream_details(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        user_id = await data.user(tier="basic")
        basic = await data.model(min_tier="basic", prices=("1000", "2000", "0", "0"))
        advanced = await data.model(min_tier="advanced")
        async with dashboard(gateway_factory, user_id) as client:
            response = await client.get("/app/api/models")
    assert response.status_code == 200
    names = {m["name"] for m in response.json()}
    assert basic in names and advanced not in names
    entry = next(m for m in response.json() if m["name"] == basic)
    assert entry["price_input_per_m"] == "1000.00"
    assert "upstream_id" not in entry and "provider" not in entry
    assert "fake/" not in response.text and "fakeprovider" not in response.text


async def test_suspended_user_cannot_use_dashboard(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user_id = await data.user(status="suspended")
        async with dashboard(gateway_factory, user_id) as client:
            response = await client.get("/app/api/keys")
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_inactive"
