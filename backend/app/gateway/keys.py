"""Portal API keys: generation, hashing, and cached lookup (FR-2.2, FR-2.3, FR-3.1, FR-3.2)."""

import hashlib
import hmac
import json
import secrets
import string
import uuid
from dataclasses import asdict, dataclass

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ApiKey, User

KEY_PREFIX = "sk-ath-"
KEY_RANDOM_LENGTH = 40
KEY_DISPLAY_PREFIX_LENGTH = 12
KEY_CACHE_TTL_S = 60
_BASE62 = string.ascii_letters + string.digits


def generate_key() -> str:
    return KEY_PREFIX + "".join(secrets.choice(_BASE62) for _ in range(KEY_RANDOM_LENGTH))


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def display_prefix(key: str) -> str:
    return key[:KEY_DISPLAY_PREFIX_LENGTH]


def looks_like_key(value: str) -> bool:
    return (
        value.startswith(KEY_PREFIX)
        and len(value) == len(KEY_PREFIX) + KEY_RANDOM_LENGTH
        and all(char in _BASE62 for char in value[len(KEY_PREFIX) :])
    )


def _cache_key(key_hash: str) -> str:
    return f"apikey:{key_hash}"


@dataclass(frozen=True)
class KeyIdentity:
    """Everything the gateway needs about a key and its owner, except the live balance."""

    api_key_id: uuid.UUID
    user_id: uuid.UUID
    key_hash: str
    key_active: bool
    user_active: bool
    user_tier: str
    user_daily_cap_idr: int | None
    key_daily_cap_idr: int | None
    model_allowlist: tuple[str, ...] | None

    @property
    def usable(self) -> bool:
        return self.key_active and self.user_active

    def to_json(self) -> str:
        data = asdict(self)
        data["api_key_id"] = str(self.api_key_id)
        data["user_id"] = str(self.user_id)
        return json.dumps(data)

    @classmethod
    def from_json(cls, raw: str | bytes) -> "KeyIdentity":
        data = json.loads(raw)
        allowlist = data["model_allowlist"]
        return cls(
            api_key_id=uuid.UUID(data["api_key_id"]),
            user_id=uuid.UUID(data["user_id"]),
            key_hash=data["key_hash"],
            key_active=data["key_active"],
            user_active=data["user_active"],
            user_tier=data["user_tier"],
            user_daily_cap_idr=data["user_daily_cap_idr"],
            key_daily_cap_idr=data["key_daily_cap_idr"],
            model_allowlist=None if allowlist is None else tuple(allowlist),
        )


def extract_presented_key(authorization: str | None, x_api_key: str | None) -> str | None:
    """Read the portal key from `Authorization: Bearer` or `x-api-key` (FR-3.1)."""
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    if authorization:
        scheme, _, credentials = authorization.partition(" ")
        if scheme.lower() == "bearer" and credentials.strip():
            return credentials.strip()
    return None


async def _load_identity(session: AsyncSession, key_hash: str) -> KeyIdentity | None:
    row = (
        await session.execute(
            select(ApiKey, User)
            .join(User, User.id == ApiKey.user_id)
            .where(ApiKey.key_hash == key_hash)
        )
    ).first()
    if row is None:
        return None
    api_key, user = row
    return KeyIdentity(
        api_key_id=api_key.id,
        user_id=user.id,
        key_hash=api_key.key_hash,
        key_active=api_key.status == "active",
        user_active=user.status == "active",
        user_tier=user.tier,
        user_daily_cap_idr=user.daily_cap_idr,
        key_daily_cap_idr=api_key.daily_cap_idr,
        model_allowlist=None if api_key.model_allowlist is None else tuple(api_key.model_allowlist),
    )


async def resolve_key(redis: Redis, session: AsyncSession, presented: str) -> KeyIdentity | None:
    """Return the identity for a presented key, or None if it is unknown or unusable.

    Redis caches the identity for 60 seconds; revoking a key or suspending a user must call
    `invalidate_keys` so the change applies instantly (FR-2.4, FR-1.5).
    """
    if not looks_like_key(presented):
        return None
    key_hash = hash_key(presented)
    cached = await redis.get(_cache_key(key_hash))
    if cached is not None:
        identity = KeyIdentity.from_json(cached)
    else:
        loaded = await _load_identity(session, key_hash)
        if loaded is None:
            return None
        identity = loaded
        await redis.set(_cache_key(key_hash), identity.to_json(), ex=KEY_CACHE_TTL_S)
    # The lookup is by hash; compare again in constant time before trusting the match.
    if not hmac.compare_digest(identity.key_hash, key_hash):
        return None
    return identity if identity.usable else None


async def invalidate_keys(redis: Redis, key_hashes: list[str]) -> None:
    if key_hashes:
        await redis.delete(*(_cache_key(key_hash) for key_hash in key_hashes))


async def invalidate_user_keys(redis: Redis, session: AsyncSession, user_id: uuid.UUID) -> None:
    hashes = (await session.scalars(select(ApiKey.key_hash).where(ApiKey.user_id == user_id))).all()
    await invalidate_keys(redis, list(hashes))
