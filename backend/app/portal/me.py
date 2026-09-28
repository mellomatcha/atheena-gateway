"""Profile of the signed-in member (§8: GET/PATCH /me)."""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.portal.deps import CurrentUser, SessionDep

router = APIRouter()


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    role: str
    tier: str
    status: str
    balance_idr: int
    low_balance_threshold_idr: int
    daily_cap_idr: int | None
    leaderboard_opt_out: bool


class MePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=60)
    low_balance_threshold_idr: int | None = Field(default=None, ge=0, le=100_000_000)
    leaderboard_opt_out: bool | None = None


def me_out(user: object) -> MeOut:
    return MeOut.model_validate(user, from_attributes=True)


@router.get("/me")
async def get_me(user: CurrentUser) -> MeOut:
    return me_out(user)


@router.patch("/me")
async def patch_me(body: MePatch, user: CurrentUser, session: SessionDep) -> MeOut:
    if body.display_name is not None:
        user.display_name = body.display_name.strip() or user.display_name
    if body.low_balance_threshold_idr is not None:
        user.low_balance_threshold_idr = body.low_balance_threshold_idr
    if body.leaderboard_opt_out is not None:
        user.leaderboard_opt_out = body.leaderboard_opt_out
    merged = await session.merge(user)
    await session.commit()
    await session.refresh(merged)
    return me_out(merged)
