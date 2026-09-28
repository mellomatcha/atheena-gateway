"""Member API keys (§8: GET/POST /keys, DELETE /keys/{id}; FR-2.x)."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.models import ApiKey, RequestLog
from app.portal.deps import CurrentUser, PortalError, SessionDep
from app.services.api_keys import ApiKeyError, create_api_key, revoke_api_key
from app.services.catalog import allowed_models

router = APIRouter()


class KeyUsage(BaseModel):
    requests: int
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int
    cache_read_tokens: int
    cost_idr: int


class KeyOut(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    status: str
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
    daily_cap_idr: int | None
    model_allowlist: list[str] | None
    usage: KeyUsage


class KeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    daily_cap_idr: int | None = Field(default=None, gt=0)
    model_allowlist: list[str] | None = Field(default=None, max_length=100)


class KeyCreated(KeyOut):
    # Shown exactly once; the portal only keeps the hash (FR-2.2, FR-2.3).
    key: str


_EMPTY_USAGE = KeyUsage(
    requests=0,
    input_tokens=0,
    output_tokens=0,
    cache_write_tokens=0,
    cache_read_tokens=0,
    cost_idr=0,
)


def _key_out(api_key: ApiKey, usage: KeyUsage) -> KeyOut:
    return KeyOut(
        id=api_key.id,
        name=api_key.name,
        prefix=api_key.key_prefix,
        status=api_key.status,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        revoked_at=api_key.revoked_at,
        daily_cap_idr=api_key.daily_cap_idr,
        model_allowlist=api_key.model_allowlist,
        usage=usage,
    )


@router.get("/keys")
async def list_keys(user: CurrentUser, session: SessionDep) -> list[KeyOut]:
    keys = (
        await session.scalars(
            select(ApiKey)
            .where(ApiKey.user_id == user.id)
            .order_by(ApiKey.status, ApiKey.created_at.desc())
        )
    ).all()
    totals = {
        row.api_key_id: KeyUsage(
            requests=row.requests,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            cache_write_tokens=row.cache_write_tokens,
            cache_read_tokens=row.cache_read_tokens,
            cost_idr=row.cost_idr,
        )
        for row in await session.execute(
            select(
                RequestLog.api_key_id,
                func.count().label("requests"),
                func.coalesce(func.sum(RequestLog.input_tokens), 0).label("input_tokens"),
                func.coalesce(func.sum(RequestLog.output_tokens), 0).label("output_tokens"),
                func.coalesce(func.sum(RequestLog.cache_write_tokens), 0).label(
                    "cache_write_tokens"
                ),
                func.coalesce(func.sum(RequestLog.cache_read_tokens), 0).label("cache_read_tokens"),
                func.coalesce(func.sum(RequestLog.cost_idr), 0).label("cost_idr"),
            )
            .where(RequestLog.user_id == user.id, RequestLog.api_key_id.is_not(None))
            .group_by(RequestLog.api_key_id)
        )
    }
    return [_key_out(key, totals.get(key.id, _EMPTY_USAGE)) for key in keys]


@router.post("/keys", status_code=201)
async def create_key(body: KeyCreate, user: CurrentUser, session: SessionDep) -> KeyCreated:
    if body.model_allowlist is not None:
        # The allowlist can only narrow the tier (FR-2.7).
        permitted = {m.public_name for m in await allowed_models(session, user.tier)}
        unknown = sorted(set(body.model_allowlist) - permitted)
        if unknown:
            raise PortalError(
                400,
                "invalid_allowlist",
                f"Model tidak tersedia untuk akun ini: {', '.join(unknown)}.",
            )
    try:
        created = await create_api_key(
            session,
            user,
            body.name,
            daily_cap_idr=body.daily_cap_idr,
            model_allowlist=body.model_allowlist,
        )
    except ApiKeyError as exc:
        raise PortalError(400 if exc.code != "key_limit" else 409, exc.code, exc.message) from exc
    await session.commit()
    await session.refresh(created.api_key)
    out = _key_out(created.api_key, _EMPTY_USAGE)
    return KeyCreated(**out.model_dump(), key=created.plaintext)


@router.delete("/keys/{key_id}")
async def revoke_key(
    key_id: uuid.UUID, request: Request, user: CurrentUser, session: SessionDep
) -> KeyOut:
    try:
        api_key = await revoke_api_key(session, request.app.state.redis, user.id, key_id)
    except ApiKeyError as exc:
        raise PortalError(404, exc.code, exc.message) from exc
    await session.commit()
    await session.refresh(api_key)
    return _key_out(api_key, _EMPTY_USAGE)
