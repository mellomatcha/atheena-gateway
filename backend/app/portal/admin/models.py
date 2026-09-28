"""Model catalog and prices (FR-4.1 to FR-4.5, FR-7.5)."""

import re
import uuid
from decimal import Decimal
from typing import Literal

import httpx
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.config import Settings
from app.ids import new_id
from app.models import AIModel
from app.models.catalog import PRICE_COLUMNS
from app.net import client_ip_hash
from app.portal.deps import AdminUser, PortalError, SessionDep
from app.services.audit import record_audit

router = APIRouter()

# Public names never carry a provider prefix (FR-4.0): lowercase letters, digits, dots, dashes.
PUBLIC_NAME = re.compile(r"^[a-z0-9][a-z0-9.\-]{0,62}$")
MAX_PRICE = Decimal("999999999999.99")

ApiFormat = Literal["openai", "anthropic", "both"]
Category = Literal["official", "experimental"]
Tier = Literal["basic", "advanced"]

EDITABLE = (
    "public_name",
    "upstream_id",
    "api_format",
    "provider",
    "category",
    "min_tier",
    "is_active",
    "context_window",
    *PRICE_COLUMNS,
)


class ModelAdminOut(BaseModel):
    """Admin view: includes upstream_id and provider, which members never see (FR-4.0)."""

    id: uuid.UUID
    public_name: str
    upstream_id: str
    api_format: str
    provider: str
    category: str
    min_tier: str
    is_active: bool
    context_window: int | None
    price_input_per_m: Decimal
    price_output_per_m: Decimal
    price_cache_write_per_m: Decimal
    price_cache_read_per_m: Decimal


def _price() -> Decimal:
    return Field(default=Decimal(0), ge=0, le=MAX_PRICE, decimal_places=2)


class ModelCreate(BaseModel):
    public_name: str
    upstream_id: str = Field(min_length=1, max_length=200)
    api_format: ApiFormat = "both"
    provider: str = Field(min_length=1, max_length=60)
    category: Category
    min_tier: Tier = "basic"
    # FR-4.5: models added from the upstream list start inactive.
    is_active: bool = False
    context_window: int | None = Field(default=None, gt=0)
    price_input_per_m: Decimal = _price()
    price_output_per_m: Decimal = _price()
    price_cache_write_per_m: Decimal = _price()
    price_cache_read_per_m: Decimal = _price()

    @field_validator("public_name")
    @classmethod
    def _valid_public_name(cls, value: str) -> str:
        value = value.strip().lower()
        if not PUBLIC_NAME.match(value):
            raise ValueError(
                "nama publik hanya huruf kecil, angka, titik, dan strip, tanpa prefix provider"
            )
        return value


class ModelPatch(BaseModel):
    public_name: str | None = None
    upstream_id: str | None = Field(default=None, min_length=1, max_length=200)
    api_format: ApiFormat | None = None
    provider: str | None = Field(default=None, min_length=1, max_length=60)
    category: Category | None = None
    min_tier: Tier | None = None
    is_active: bool | None = None
    context_window: int | None = Field(default=None, gt=0)
    price_input_per_m: Decimal | None = Field(default=None, ge=0, le=MAX_PRICE, decimal_places=2)
    price_output_per_m: Decimal | None = Field(default=None, ge=0, le=MAX_PRICE, decimal_places=2)
    price_cache_write_per_m: Decimal | None = Field(
        default=None, ge=0, le=MAX_PRICE, decimal_places=2
    )
    price_cache_read_per_m: Decimal | None = Field(
        default=None, ge=0, le=MAX_PRICE, decimal_places=2
    )

    @field_validator("public_name")
    @classmethod
    def _valid_public_name(cls, value: str | None) -> str | None:
        return None if value is None else ModelCreate._valid_public_name(value)


def _snapshot(model: AIModel) -> dict[str, object]:
    # JSON-friendly: prices as strings so the audit log keeps exact values.
    return {
        field: str(value) if isinstance(value, Decimal) else value
        for field in EDITABLE
        for value in [getattr(model, field)]
    }


def _out(model: AIModel) -> ModelAdminOut:
    return ModelAdminOut.model_validate(model, from_attributes=True)


@router.get("/models")
async def list_models(admin: AdminUser, session: SessionDep) -> list[ModelAdminOut]:
    models = (await session.scalars(select(AIModel).order_by(AIModel.public_name))).all()
    return [_out(m) for m in models]


@router.post("/models", status_code=201)
async def create_model(
    body: ModelCreate, request: Request, admin: AdminUser, session: SessionDep
) -> ModelAdminOut:
    if await session.scalar(select(AIModel.id).where(AIModel.public_name == body.public_name)):
        raise PortalError(409, "name_taken", "Nama publik ini sudah dipakai model lain.")
    model = AIModel(id=new_id(), **body.model_dump())
    session.add(model)
    await session.flush()
    await record_audit(
        session,
        actor_user_id=admin.id,
        action="model.create",
        target_type="model",
        target_id=str(model.id),
        after=_snapshot(model),
        ip_hash=client_ip_hash(request),
    )
    await session.commit()
    await session.refresh(model)
    return _out(model)


@router.patch("/models/{model_id}")
async def update_model(
    model_id: uuid.UUID,
    body: ModelPatch,
    request: Request,
    admin: AdminUser,
    session: SessionDep,
) -> ModelAdminOut:
    model = await session.get(AIModel, model_id, with_for_update=True)
    if model is None:
        raise PortalError(404, "model_not_found", "Model tidak ditemukan.")
    changes = body.model_dump(exclude_unset=True)
    new_name = changes.get("public_name")
    if new_name and new_name != model.public_name:
        taken = await session.scalar(select(AIModel.id).where(AIModel.public_name == new_name))
        if taken:
            raise PortalError(409, "name_taken", "Nama publik ini sudah dipakai model lain.")
    before = _snapshot(model)
    for field, value in changes.items():
        if value is None and field != "context_window":
            continue
        setattr(model, field, value)
    await session.flush()
    after = _snapshot(model)
    changed = [k for k in EDITABLE if before[k] != after[k]]
    if changed:
        price_changed = any(k in PRICE_COLUMNS for k in changed)
        await record_audit(
            session,
            actor_user_id=admin.id,
            # FR-4.3: price changes are called out so they are easy to find in the log.
            action="model.price_update" if price_changed else "model.update",
            target_type="model",
            target_id=str(model.id),
            before={k: before[k] for k in changed},
            after={k: after[k] for k in changed},
            ip_hash=client_ip_hash(request),
        )
    await session.commit()
    await session.refresh(model)
    return _out(model)


class SyncCandidate(BaseModel):
    upstream_id: str
    owned_by: str | None
    suggested_public_name: str


class SyncOut(BaseModel):
    upstream_total: int
    in_catalog: int
    candidates: list[SyncCandidate]


def suggest_public_name(upstream_id: str) -> str:
    """'cb/claude-sonnet-4.6' -> 'claude-sonnet-4.6' (admin can still change it)."""
    name = upstream_id.rsplit("/", 1)[-1].lower()
    name = re.sub(r"[^a-z0-9.\-]", "-", name).strip("-.")
    return name[:63] or "model"


@router.post("/models/sync")
async def sync_models(request: Request, admin: AdminUser, session: SessionDep) -> SyncOut:
    """FR-4.5: list upstream models that are not in the catalog yet. Nothing is added."""
    settings: Settings = request.app.state.settings
    try:
        response = await request.app.state.upstream.get(
            f"{settings.upstream_base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {settings.upstream_api_key.get_secret_value()}"},
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise PortalError(502, "upstream_unreachable", "9Router tidak bisa dihubungi.") from exc
    if response.status_code != 200:
        raise PortalError(
            502, "upstream_error", f"9Router mengembalikan HTTP {response.status_code}."
        )
    data = response.json().get("data", [])
    upstream = {
        item["id"]: item.get("owned_by") for item in data if isinstance(item.get("id"), str)
    }
    known = set((await session.scalars(select(AIModel.upstream_id))).all())
    candidates = [
        SyncCandidate(
            upstream_id=uid, owned_by=owner, suggested_public_name=suggest_public_name(uid)
        )
        for uid, owner in sorted(upstream.items())
        if uid not in known
    ]
    return SyncOut(
        upstream_total=len(upstream),
        in_catalog=len(upstream) - len(candidates),
        candidates=candidates,
    )
