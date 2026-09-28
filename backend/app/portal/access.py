"""Cloudflare Access JWT verification (FR-1.1, FR-1.2).

The `Cf-Access-Jwt-Assertion` token is verified against the team's public keys instead of
trusting the email header, so a request that bypasses the tunnel cannot impersonate anyone.
"""

import logging
import time
from typing import Any

import httpx
import jwt

logger = logging.getLogger(__name__)

# Unknown key ids trigger a refetch (Cloudflare rotates keys), but at most this often.
MIN_REFRESH_INTERVAL_S = 60.0
# Known keys are refreshed after this long even when no unknown kid shows up.
MAX_KEY_AGE_S = 3600.0


class AccessDeniedError(Exception):
    """The token is missing, invalid, or not for this application. Reason is safe to log."""


def normalize_team_domain(value: str) -> str:
    return value.strip().removeprefix("https://").removeprefix("http://").rstrip("/")


class AccessVerifier:
    def __init__(self, client: httpx.AsyncClient, team_domain: str, audience: str) -> None:
        self.client = client
        self.team_domain = normalize_team_domain(team_domain)
        self.audience = audience
        self.issuer = f"https://{self.team_domain}"
        self.certs_url = f"{self.issuer}/cdn-cgi/access/certs"
        # Public keys only: a cache that any replica can rebuild, not shared state.
        self._keys: dict[str, Any] = {}
        self._fetched_at = 0.0

    async def _refresh(self) -> None:
        response = await self.client.get(self.certs_url)
        response.raise_for_status()
        keys: dict[str, Any] = {}
        for jwk in response.json().get("keys", []):
            kid = jwk.get("kid")
            if kid:
                keys[kid] = jwt.PyJWK(jwk).key
        self._keys = keys
        self._fetched_at = time.monotonic()

    async def _key_for(self, kid: str) -> Any:
        age = time.monotonic() - self._fetched_at
        if (kid not in self._keys and age >= MIN_REFRESH_INTERVAL_S) or age >= MAX_KEY_AGE_S:
            try:
                await self._refresh()
            except (httpx.HTTPError, ValueError, jwt.PyJWKError) as exc:
                logger.warning("access certs fetch failed", extra={"exc_type": type(exc).__name__})
        key = self._keys.get(kid)
        if key is None:
            raise AccessDeniedError("unknown signing key")
        return key

    async def verify(self, token: str) -> str:
        """Return the lower-cased email of a valid token, or raise AccessDeniedError."""
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise AccessDeniedError("malformed token") from exc
        kid = header.get("kid")
        if not isinstance(kid, str) or header.get("alg") != "RS256":
            raise AccessDeniedError("unexpected token header")
        key = await self._key_for(kid)
        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options={"require": ["exp", "aud", "iss"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AccessDeniedError("token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AccessDeniedError(f"invalid token ({type(exc).__name__})") from exc
        email = claims.get("email")
        if not isinstance(email, str) or "@" not in email:
            raise AccessDeniedError("token has no email")
        return email.strip().lower()
