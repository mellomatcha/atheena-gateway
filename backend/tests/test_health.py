import uuid

import httpx
import respx

from tests.conftest import FAKE_UPSTREAM, FAKE_UPSTREAM_KEY, ClientFactory

MODELS_URL = f"{FAKE_UPSTREAM}/models"


async def test_healthz_returns_ok_and_request_id(client_factory: ClientFactory) -> None:
    async with client_factory() as client:
        response = await client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    request_id = uuid.UUID(response.headers["x-request-id"])
    assert request_id.version == 7


@respx.mock(assert_all_mocked=False)
async def test_readyz_all_healthy(
    client_factory: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(MODELS_URL).mock(
        return_value=httpx.Response(200, json={"object": "list", "data": []})
    )
    async with client_factory() as client:
        response = await client.get("/readyz")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert {name: check["ok"] for name, check in body["checks"].items()} == {
        "postgres": True,
        "redis": True,
        "upstream": True,
    }
    assert route.calls.last.request.headers["authorization"] == f"Bearer {FAKE_UPSTREAM_KEY}"


@respx.mock(assert_all_mocked=False)
async def test_readyz_upstream_down(
    client_factory: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(MODELS_URL).mock(side_effect=httpx.ConnectError("connection refused"))
    async with client_factory() as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "fail"
    assert body["checks"]["postgres"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is True
    assert body["checks"]["upstream"] == {"ok": False, "error": "ConnectError"}


@respx.mock(assert_all_mocked=False)
async def test_readyz_upstream_rejects_key(
    client_factory: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(MODELS_URL).mock(
        return_value=httpx.Response(401, json={"error": "secret upstream detail"})
    )
    async with client_factory() as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    upstream = response.json()["checks"]["upstream"]
    assert upstream == {"ok": False, "error": "upstream returned HTTP 401"}
    assert "secret upstream detail" not in response.text


@respx.mock(assert_all_mocked=False)
async def test_readyz_redis_and_postgres_down(
    client_factory: ClientFactory, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(MODELS_URL).mock(return_value=httpx.Response(200, json={"data": []}))
    async with client_factory(
        redis_url="redis://127.0.0.1:1/0",
        database_url="postgresql+asyncpg://agent@/does_not_exist?host=/var/run/postgresql",
    ) as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    checks = response.json()["checks"]
    assert checks["postgres"]["ok"] is False
    assert checks["redis"]["ok"] is False
    assert checks["upstream"]["ok"] is True
