"""Leaderboard for every member (§8: GET /leaderboard; FR-8.x)."""

from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from app.portal.deps import CurrentUser, SessionDep
from app.services.leaderboard import EFFICIENCY_MIN_REQUESTS, Metric, Period, leaderboard

router = APIRouter()


class EntryOut(BaseModel):
    rank: int
    # FR-8.3: display name only, never the email.
    display_name: str
    value: float
    requests: int
    is_me: bool


class LeaderboardOut(BaseModel):
    period: Period
    metric: Metric
    start: date
    end: date
    entries: list[EntryOut]
    me_opted_out: bool
    efficiency_min_requests: int


@router.get("/leaderboard")
async def get_leaderboard(
    user: CurrentUser,
    session: SessionDep,
    period: Period = "week",
    metric: Metric = "tokens",
) -> LeaderboardOut:
    start, end, entries = await leaderboard(session, period, metric)
    return LeaderboardOut(
        period=period,
        metric=metric,
        start=start,
        end=end,
        entries=[
            EntryOut(
                rank=e.rank,
                display_name=e.display_name,
                value=e.value,
                requests=e.requests,
                is_me=e.user_id == user.id,
            )
            for e in entries
        ],
        me_opted_out=user.leaderboard_opt_out,
        efficiency_min_requests=EFFICIENCY_MIN_REQUESTS,
    )
