"""Profile of the signed-in member (§8: GET/PATCH /me)."""

import re
import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError

from app.portal.deps import PortalError, ProfileUser, SessionDep

router = APIRouter()


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    full_name: str
    username: str
    profile_completed: bool
    role: str
    tier: str
    status: str
    balance_idr: int
    low_balance_threshold_idr: int
    daily_cap_idr: int | None
    leaderboard_opt_out: bool


class MePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    full_name: str | None = Field(default=None, min_length=1, max_length=60)
    username: str | None = Field(default=None, min_length=3, max_length=24)
    low_balance_threshold_idr: int | None = Field(default=None, ge=0, le=100_000_000)
    leaderboard_opt_out: bool | None = None

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,23}", value):
            raise ValueError(
                "Username harus 3-24 karakter: huruf, angka, underscore; diawali huruf."
            )
        return value

    @field_validator("full_name", "display_name")
    @classmethod
    def valid_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Nama tidak boleh kosong.")
        return value.strip() if value else value


def me_out(user: object) -> MeOut:
    return MeOut.model_validate(user, from_attributes=True)


@router.get("/me")
async def get_me(user: ProfileUser) -> MeOut:
    return me_out(user)


@router.patch("/me")
async def patch_me(body: MePatch, user: ProfileUser, session: SessionDep) -> MeOut:
    if body.display_name is not None:
        user.display_name = body.display_name.strip() or user.display_name
    if body.full_name is not None:
        user.display_name = body.full_name
    if body.username is not None:
        user.username = body.username
    if body.username is not None:
        user.profile_completed = True
    if body.low_balance_threshold_idr is not None:
        user.low_balance_threshold_idr = body.low_balance_threshold_idr
    if body.leaderboard_opt_out is not None:
        user.leaderboard_opt_out = body.leaderboard_opt_out
    try:
        merged = await session.merge(user)
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        if "uq_users_username" in str(error.orig):
            raise PortalError(409, "username_taken", "Username ini sudah dipakai.") from error
        raise
    await session.refresh(merged)
    return me_out(merged)
