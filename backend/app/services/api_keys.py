"""API key lifecycle shared by the dashboard and the admin CLI (FR-2.1 to FR-2.7)."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.gateway.keys import display_prefix, generate_key, hash_key, invalidate_keys
from app.gateway.settings_store import load_settings
from app.ids import new_id
from app.models import ApiKey, User

KEY_NAME_MAX = 60


class ApiKeyError(Exception):
    """A key operation was refused; the message is safe to show to the user."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class CreatedKey:
    api_key: ApiKey
    plaintext: str


async def create_api_key(
    session: AsyncSession,
    user: User,
    name: str,
    *,
    daily_cap_idr: int | None = None,
    model_allowlist: list[str] | None = None,
) -> CreatedKey:
    """Create a key; the plaintext is returned once and never stored (FR-2.2, FR-2.3)."""
    name = name.strip()
    if not name or len(name) > KEY_NAME_MAX:
        raise ApiKeyError(
            "invalid_name", f"Nama key wajib diisi, maksimal {KEY_NAME_MAX} karakter."
        )
    if daily_cap_idr is not None and daily_cap_idr <= 0:
        raise ApiKeyError("invalid_cap", "Batas biaya harian harus lebih dari 0.")
    # Serialize key creation per user so two parallel requests cannot exceed the limit.
    await session.execute(select(User.id).where(User.id == user.id).with_for_update())
    active = await session.scalar(
        select(func.count()).where(ApiKey.user_id == user.id, ApiKey.status == "active")
    )
    limit = int((await load_settings(session))["max_active_keys_per_user"])
    if (active or 0) >= limit:
        raise ApiKeyError("key_limit", f"Maksimal {limit} key aktif per user. Cabut key lama dulu.")
    plaintext = generate_key()
    api_key = ApiKey(
        id=new_id(),
        user_id=user.id,
        name=name,
        key_hash=hash_key(plaintext),
        key_prefix=display_prefix(plaintext),
        daily_cap_idr=daily_cap_idr,
        model_allowlist=sorted(set(model_allowlist)) if model_allowlist else None,
    )
    session.add(api_key)
    await session.flush()
    return CreatedKey(api_key=api_key, plaintext=plaintext)


async def revoke_api_key(
    session: AsyncSession, redis: Redis, user_id: uuid.UUID, key_id: uuid.UUID
) -> ApiKey:
    """Revoke one of the user's keys and drop its cache entry so it fails at once (FR-2.4)."""
    api_key = await session.scalar(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id).with_for_update()
    )
    if api_key is None:
        raise ApiKeyError("not_found", "Key tidak ditemukan.")
    if api_key.status != "revoked":
        api_key.status = "revoked"
        api_key.revoked_at = datetime.now(UTC)
        await session.flush()
    await invalidate_keys(redis, [api_key.key_hash])
    return api_key
