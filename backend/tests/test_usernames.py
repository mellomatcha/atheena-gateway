"""Public usernames are unique and independent of private full names."""

import asyncio

import pytest

from tests.conftest import ClientFactory
from tests.gateway_support import gateway_data
from tests.test_usage import as_user


async def test_profile_separates_full_name_and_normalizes_username(
    gateway_factory: ClientFactory,
) -> None:
    async with gateway_data() as data:
        user = await data.user()
        async with as_user(gateway_factory, user) as client:
            result = await client.patch(
                "/app/api/me", json={"full_name": "Private Person", "username": "Athena_User"}
            )
            assert result.status_code == 200
            profile = (await client.get("/app/api/me")).json()
            assert profile["full_name"] == "Private Person"
            assert profile["username"] == "athena_user"


async def test_concurrent_username_claim_only_one_succeeds(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        first, second = await data.user(), await data.user()
        async with as_user(gateway_factory, first) as a, as_user(gateway_factory, second) as b:
            responses = await asyncio.gather(
                a.patch("/app/api/me", json={"username": "shared_handle"}),
                b.patch("/app/api/me", json={"username": "shared_handle"}),
            )
            assert sorted(r.status_code for r in responses) == [200, 409]
            conflict = next(r for r in responses if r.status_code == 409)
            assert conflict.json()["error"]["code"] == "username_taken"


@pytest.mark.parametrize("value", ["ab", "1name", "name space", "name@site", "a" * 25])
async def test_invalid_username(gateway_factory: ClientFactory, value: str) -> None:
    async with gateway_data() as data:
        user = await data.user()
        async with as_user(gateway_factory, user) as client:
            response = await client.patch("/app/api/me", json={"username": value})
        assert response.status_code == 422


async def test_profile_required_before_key_creation(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        user = await data.user(profile_completed=False)
        async with as_user(gateway_factory, user) as client:
            denied = await client.post("/app/api/keys", json={"name": "laptop"})
            assert denied.status_code == 403
            assert denied.json()["error"]["code"] == "profile_incomplete"
            completed = await client.patch("/app/api/me", json={"username": "new_member"})
            assert completed.json()["profile_completed"] is True
            created = await client.post("/app/api/keys", json={"name": "laptop"})
            assert created.status_code == 201


async def test_taken_username_does_not_complete_profile(gateway_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        first, second = await data.user(), await data.user(profile_completed=False)
        async with as_user(gateway_factory, first) as client:
            await client.patch("/app/api/me", json={"username": "reserved_user"})
        async with as_user(gateway_factory, second) as client:
            conflict = await client.patch(
                "/app/api/me", json={"full_name": "Private Member", "username": "reserved_user"}
            )
            assert conflict.status_code == 409
            assert (await client.get("/app/api/me")).json()["profile_completed"] is False
