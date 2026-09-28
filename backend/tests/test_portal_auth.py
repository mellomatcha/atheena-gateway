"""Cloudflare Access authentication for the dashboard API (FR-1.1 to FR-1.3, §11)."""

import time
from typing import Any

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from pydantic import ValidationError

from app.portal.deps import PortalError, require_admin
from tests.conftest import ClientFactory, make_settings
from tests.gateway_support import gateway_data

TEAM = "atheena-test.cloudflareaccess.com"
AUD = "test-aud-tag-0123456789"
CERTS_URL = f"https://{TEAM}/cdn-cgi/access/certs"
CF = {"cf_access_team_domain": TEAM, "cf_access_aud": AUD}
CSRF = {"X-Atheena-CSRF": "1"}

SIGNING_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KID = "kid-current"


def jwks() -> dict[str, Any]:
    public = jwt.algorithms.RSAAlgorithm.to_jwk(SIGNING_KEY.public_key(), as_dict=True)
    return {"keys": [{**public, "kid": KID, "alg": "RS256", "use": "sig"}]}


def token(
    email: str,
    *,
    aud: str = AUD,
    iss: str = f"https://{TEAM}",
    exp_in: int = 600,
    key: rsa.RSAPrivateKey = SIGNING_KEY,
    kid: str = KID,
    **extra: Any,
) -> str:
    now = int(time.time())
    claims = {"email": email, "aud": [aud], "iss": iss, "iat": now, "exp": now + exp_in, **extra}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def email_of(user_id: object) -> str:
    return f"u-{user_id}@example.test"


@pytest.fixture
def certs() -> Any:
    with respx.mock(assert_all_mocked=False, assert_all_called=False) as mock:
        route = mock.get(CERTS_URL).mock(return_value=httpx.Response(200, json=jwks()))
        yield route


async def test_valid_token_identifies_active_user(
    client_factory: ClientFactory, certs: respx.Route
) -> None:
    async with gateway_data() as data:
        user_id = await data.user(balance=12_345)
        async with client_factory(**CF) as client:
            response = await client.get(
                "/app/api/me", headers={"Cf-Access-Jwt-Assertion": token(email_of(user_id))}
            )
            client.cookies.set("CF_Authorization", token(email_of(user_id)))
            cookie = await client.get("/app/api/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == email_of(user_id)
    assert body["balance_idr"] == 12_345
    assert cookie.status_code == 200
    # Keys are cached in-process after the first fetch.
    assert certs.call_count == 1


async def test_email_claim_is_case_insensitive(
    client_factory: ClientFactory, certs: respx.Route
) -> None:
    async with gateway_data() as data:
        user_id = await data.user()
        async with client_factory(**CF) as client:
            response = await client.get(
                "/app/api/me",
                headers={"Cf-Access-Jwt-Assertion": token(email_of(user_id).upper())},
            )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "bad_token",
    [
        pytest.param(lambda e: token(e, aud="another-app"), id="wrong-aud"),
        pytest.param(lambda e: token(e, iss="https://evil.cloudflareaccess.com"), id="wrong-iss"),
        pytest.param(lambda e: token(e, exp_in=-60), id="expired"),
        pytest.param(lambda e: token(e, key=OTHER_KEY), id="bad-signature"),
        pytest.param(lambda e: token(e, kid="kid-unknown", key=OTHER_KEY), id="unknown-kid"),
        pytest.param(
            lambda e: jwt.encode(
                {"email": e, "aud": AUD}, "s" * 32, algorithm="HS256", headers={"kid": KID}
            ),
            id="hs256",
        ),
        pytest.param(lambda e: "not.a.jwt", id="malformed"),
        pytest.param(
            lambda e: jwt.encode(
                {"aud": [AUD], "iss": f"https://{TEAM}", "exp": int(time.time()) + 600},
                SIGNING_KEY,
                algorithm="RS256",
                headers={"kid": KID},
            ),
            id="no-email",
        ),
    ],
)
async def test_invalid_tokens_are_401(
    client_factory: ClientFactory, certs: respx.Route, bad_token: Any
) -> None:
    async with gateway_data() as data:
        user_id = await data.user()
        async with client_factory(**CF) as client:
            response = await client.get(
                "/app/api/me", headers={"Cf-Access-Jwt-Assertion": bad_token(email_of(user_id))}
            )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_email_header_alone_is_not_trusted(
    client_factory: ClientFactory, certs: respx.Route
) -> None:
    """FR-1.2: the email header without a valid JWT is rejected."""
    async with gateway_data() as data:
        user_id = await data.user()
        async with client_factory(**CF) as client:
            header_only = await client.get(
                "/app/api/me", headers={"Cf-Access-Authenticated-User-Email": email_of(user_id)}
            )
            mismatch = await client.get(
                "/app/api/me",
                headers={
                    "Cf-Access-Jwt-Assertion": token(email_of(user_id)),
                    "Cf-Access-Authenticated-User-Email": "someone-else@example.test",
                },
            )
    assert header_only.status_code == 401
    assert mismatch.status_code == 401


@pytest.mark.parametrize("status", ["suspended", "pending", None])
async def test_access_without_active_account_is_403(
    client_factory: ClientFactory, certs: respx.Route, status: str | None
) -> None:
    """FR-1.3: passing Cloudflare Access is not enough."""
    async with gateway_data() as data:
        if status is None:
            email = "not-registered@example.test"
        else:
            email = email_of(await data.user(status=status))
        async with client_factory(**CF) as client:
            response = await client.get(
                "/app/api/me", headers={"Cf-Access-Jwt-Assertion": token(email)}
            )
    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "account_inactive",
        "message": "Akun belum aktif, hubungi admin.",
    }


async def test_rotated_key_is_fetched_on_unknown_kid(client_factory: ClientFactory) -> None:
    import app.portal.access as access

    rotated = jwt.algorithms.RSAAlgorithm.to_jwk(OTHER_KEY.public_key(), as_dict=True)
    async with gateway_data() as data:
        user_id = await data.user()
        with respx.mock(assert_all_mocked=False) as mock:
            route = mock.get(CERTS_URL).mock(
                side_effect=[
                    httpx.Response(200, json=jwks()),
                    httpx.Response(
                        200, json={"keys": [*jwks()["keys"], {**rotated, "kid": "kid-new"}]}
                    ),
                ]
            )
            original = access.MIN_REFRESH_INTERVAL_S
            access.MIN_REFRESH_INTERVAL_S = 0
            try:
                async with client_factory(**CF) as client:
                    first = await client.get(
                        "/app/api/me", headers={"Cf-Access-Jwt-Assertion": token(email_of(user_id))}
                    )
                    rotated_response = await client.get(
                        "/app/api/me",
                        headers={
                            "Cf-Access-Jwt-Assertion": token(
                                email_of(user_id), key=OTHER_KEY, kid="kid-new"
                            )
                        },
                    )
            finally:
                access.MIN_REFRESH_INTERVAL_S = original
    assert first.status_code == 200
    assert rotated_response.status_code == 200
    assert route.call_count == 2


async def test_dev_bypass_works_only_in_development(client_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        email = email_of(await data.user())
        async with client_factory(app_env="development", dev_auth_email=email) as client:
            dev = await client.get("/app/api/me")
        async with client_factory(app_env="test", dev_auth_email=email) as client:
            test_env = await client.get("/app/api/me")
    assert dev.status_code == 200
    assert dev.json()["email"] == email
    assert test_env.status_code == 401


async def test_dev_bypass_is_off_in_production(
    client_factory: ClientFactory, certs: respx.Route
) -> None:
    """The bypass can never be active in production: startup refuses DEV_AUTH_EMAIL."""
    with pytest.raises(ValidationError, match="DEV_AUTH_EMAIL must not be set"):
        make_settings(app_env="production", dev_auth_email="admin@example.test", **CF)
    with pytest.raises(ValidationError, match="DEV_AUTH_EMAIL must not be set"):
        make_settings(app_env="prod", dev_auth_email="admin@example.test", **CF)
    with pytest.raises(ValidationError, match="CF_ACCESS_TEAM_DOMAIN and CF_ACCESS_AUD"):
        make_settings(app_env="production")

    # Even if the property were consulted, production never yields a bypass email.
    settings = make_settings(app_env="production", **CF)
    assert settings.dev_auth_bypass_email is None

    async with gateway_data() as data:
        email = email_of(await data.user())
        async with client_factory(app_env="production", **CF) as client:
            no_token = await client.get("/app/api/me")
            with_token = await client.get(
                "/app/api/me", headers={"Cf-Access-Jwt-Assertion": token(email)}
            )
    assert no_token.status_code == 401
    assert with_token.status_code == 200


def test_app_env_aliases() -> None:
    assert make_settings(app_env="dev").app_env == "development"
    assert make_settings(app_env="prod", **CF).app_env == "production"
    assert make_settings(app_env="dev", dev_auth_email="  ").dev_auth_bypass_email is None


async def test_require_admin_checks_role() -> None:
    from app.models import User

    member = User(email="m@example.test", display_name="M", role="member", status="active")
    admin = User(email="a@example.test", display_name="A", role="admin", status="active")
    assert await require_admin(admin) is admin
    with pytest.raises(PortalError) as excinfo:
        await require_admin(member)
    assert excinfo.value.status_code == 403


async def test_mutations_require_csrf_header(client_factory: ClientFactory) -> None:
    async with gateway_data() as data:
        email = email_of(await data.user())
        async with client_factory(app_env="development", dev_auth_email=email) as client:
            missing = await client.patch("/app/api/me", json={"display_name": "X"})
            cross_origin = await client.patch(
                "/app/api/me",
                json={"display_name": "X"},
                headers={**CSRF, "Origin": "https://evil.example"},
            )
            same_origin = await client.patch(
                "/app/api/me",
                json={"display_name": "Nama Baru"},
                headers={**CSRF, "Origin": "http://test"},
            )
            read_only = await client.get("/app/api/me")
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_failed"
    assert cross_origin.status_code == 403
    assert same_origin.status_code == 200
    assert same_origin.json()["display_name"] == "Nama Baru"
    assert read_only.status_code == 200
