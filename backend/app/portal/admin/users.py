"""User management by an admin (FR-1.4, FR-1.5, FR-7.1)."""

import re
import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select

from app.gateway.keys import invalidate_user_keys
from app.ids import new_id
from app.models import ApiKey, User
from app.net import client_ip_hash
from app.portal.deps import AdminUser, PortalError, SessionDep
from app.services.audit import record_audit

router = APIRouter()

Tier = Literal["basic", "advanced"]
Role = Literal["member", "admin"]
Status = Literal["active", "suspended", "pending"]


class UserDetail(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    tier: str
    status: str
    balance_idr: int
    daily_cap_idr: int | None
    leaderboard_opt_out: bool
    created_at: datetime
    active_keys: int = 0


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserCreate(BaseModel):
    email: str = Field(max_length=254)
    display_name: str = Field(min_length=1, max_length=60)
    tier: Tier = "basic"
    role: Role = "member"

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not EMAIL_PATTERN.match(value):
            raise ValueError("email tidak valid")
        return value


class UserPatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    tier: Tier | None = None
    role: Role | None = None
    status: Status | None = None
    # Explicit null clears the cap; omit the field to leave it unchanged.
    daily_cap_idr: int | None = Field(default=None, gt=0)


AUDITED_FIELDS = ("display_name", "tier", "role", "status", "daily_cap_idr")


def _snapshot(user: User) -> dict[str, object]:
    return {field: getattr(user, field) for field in AUDITED_FIELDS}


async def _detail(session: SessionDep, user: User) -> UserDetail:
    keys = await session.scalar(
        select(func.count()).where(ApiKey.user_id == user.id, ApiKey.status == "active")
    )
    return UserDetail.model_validate(
        {**UserDetail.model_validate(user, from_attributes=True).model_dump(), "active_keys": keys}
    )


@router.get("/users/{user_id}")
async def get_user(user_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> UserDetail:
    user = await session.get(User, user_id)
    if user is None:
        raise PortalError(404, "user_not_found", "User tidak ditemukan.")
    return await _detail(session, user)


@router.post("/users", status_code=201)
async def create_user(
    body: UserCreate, request: Request, admin: AdminUser, session: SessionDep
) -> UserDetail:
    email = body.email.strip().lower()
    if await session.scalar(select(User.id).where(User.email == email)):
        raise PortalError(409, "email_taken", "Email ini sudah terdaftar.")
    user = User(
        id=new_id(),
        email=email,
        display_name=body.display_name.strip(),
        tier=body.tier,
        role=body.role,
        status="active",
    )
    session.add(user)
    await session.flush()
    await record_audit(
        session,
        actor_user_id=admin.id,
        action="user.create",
        target_type="user",
        target_id=str(user.id),
        after={"email": email, **_snapshot(user)},
        ip_hash=client_ip_hash(request),
    )
    await session.commit()
    await session.refresh(user)
    return await _detail(session, user)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: uuid.UUID,
    body: UserPatch,
    request: Request,
    admin: AdminUser,
    session: SessionDep,
) -> UserDetail:
    user = await session.get(User, user_id, with_for_update=True)
    if user is None:
        raise PortalError(404, "user_not_found", "User tidak ditemukan.")
    changes = body.model_dump(exclude_unset=True)
    if user.id == admin.id and (
        changes.get("status") not in (None, "active") or changes.get("role") == "member"
    ):
        raise PortalError(
            400, "self_lockout", "Anda tidak bisa menonaktifkan atau menurunkan peran akun sendiri."
        )
    before = _snapshot(user)
    for field, value in changes.items():
        if field == "display_name" and value is not None:
            value = value.strip()
        if field != "daily_cap_idr" and value is None:
            continue
        setattr(user, field, value)
    after = _snapshot(user)
    diff_before = {k: v for k, v in before.items() if after[k] != v}
    diff_after = {k: after[k] for k in diff_before}
    if diff_before:
        await record_audit(
            session,
            actor_user_id=admin.id,
            action="user.update",
            target_type="user",
            target_id=str(user.id),
            before=diff_before,
            after=diff_after,
            ip_hash=client_ip_hash(request),
        )
    await session.commit()
    if diff_before:
        # Status, tier, and caps are cached with each key identity; drop them so a suspension
        # or tier change applies to the very next request (FR-1.5).
        await invalidate_user_keys(request.app.state.redis, session, user.id)
    await session.refresh(user)
    return await _detail(session, user)
