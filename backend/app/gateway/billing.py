"""Recording proxied requests and debiting balances (FR-3.21 to FR-3.23, FR-5.1).

Every balance change goes through a ledger entry written in the same transaction as the
`users.balance_idr` update, with the user row locked (`SELECT ... FOR UPDATE`) so parallel
requests from one user serialize instead of overwriting each other's debit.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.gateway.usage import Usage
from app.ids import new_id
from app.models import ApiKey, LedgerEntry, RequestLog, User

# Daily caps reset at midnight Western Indonesia Time (UTC+7, no daylight saving).
WIB = timezone(timedelta(hours=7), "WIB")
# last_used_at is informational; writing it at most once a minute keeps hot keys cheap.
LAST_USED_RESOLUTION = timedelta(minutes=1)


def start_of_day_wib(now: datetime | None = None) -> datetime:
    local = (now or datetime.now(UTC)).astimezone(WIB)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def seconds_until_next_day_wib(now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    next_day = start_of_day_wib(now) + timedelta(days=1)
    return max(int((next_day - now).total_seconds()), 1)


@dataclass
class RequestRecord:
    request_id: uuid.UUID
    endpoint: str
    started_at: datetime
    status_code: int
    is_stream: bool = False
    user_id: uuid.UUID | None = None
    api_key_id: uuid.UUID | None = None
    model_id: uuid.UUID | None = None
    model_public_name: str | None = None
    project: str | None = None
    error_type: str | None = None
    usage: Usage = field(default_factory=Usage)
    usage_estimated: bool = False
    price_snapshot: dict[str, Any] | None = None
    cost_idr: int = 0
    latency_ms: int | None = None
    ttft_ms: int | None = None
    client_ip_hash: str | None = None
    user_agent: str | None = None
    finished_at: datetime | None = None


async def record_request(
    sessionmaker: async_sessionmaker[AsyncSession], rec: RequestRecord
) -> None:
    """Insert the request row and, if it cost anything, the ledger debit, atomically."""
    if rec.cost_idr < 0:
        raise ValueError("cost_idr must not be negative")
    async with sessionmaker() as session, session.begin():
        if rec.cost_idr > 0:
            if rec.user_id is None:
                raise ValueError("a billed request needs a user")
            balance = await session.scalar(
                select(User.balance_idr).where(User.id == rec.user_id).with_for_update()
            )
            if balance is None:
                raise LookupError("user not found")
            new_balance = balance - rec.cost_idr
            await session.execute(
                update(User).where(User.id == rec.user_id).values(balance_idr=new_balance)
            )
            await session.execute(
                insert(LedgerEntry).values(
                    id=new_id(),
                    user_id=rec.user_id,
                    type="usage",
                    amount_idr=-rec.cost_idr,
                    balance_after_idr=new_balance,
                    request_id=rec.request_id,
                )
            )
        await session.execute(
            insert(RequestLog).values(
                id=new_id(),
                request_id=rec.request_id,
                started_at=rec.started_at,
                finished_at=rec.finished_at or datetime.now(UTC),
                user_id=rec.user_id,
                api_key_id=rec.api_key_id,
                model_id=rec.model_id,
                model_public_name=rec.model_public_name,
                project=rec.project,
                endpoint=rec.endpoint,
                is_stream=rec.is_stream,
                status_code=rec.status_code,
                error_type=rec.error_type,
                input_tokens=rec.usage.input_tokens,
                output_tokens=rec.usage.output_tokens,
                cache_write_tokens=rec.usage.cache_write_tokens,
                cache_read_tokens=rec.usage.cache_read_tokens,
                usage_estimated=rec.usage_estimated,
                price_snapshot=rec.price_snapshot,
                cost_idr=rec.cost_idr,
                latency_ms=rec.latency_ms,
                ttft_ms=rec.ttft_ms,
                client_ip_hash=rec.client_ip_hash,
                user_agent=rec.user_agent,
            )
        )
        if rec.api_key_id is not None and rec.user_id is not None:
            now = datetime.now(UTC)
            await session.execute(
                update(ApiKey)
                .where(
                    ApiKey.id == rec.api_key_id,
                    (ApiKey.last_used_at.is_(None))
                    | (ApiKey.last_used_at < now - LAST_USED_RESOLUTION),
                )
                .values(last_used_at=now)
            )


async def spent_today_idr(
    session: AsyncSession, *, user_id: uuid.UUID | None = None, api_key_id: uuid.UUID | None = None
) -> int:
    query = select(func.coalesce(func.sum(RequestLog.cost_idr), 0)).where(
        RequestLog.started_at >= start_of_day_wib()
    )
    if user_id is not None:
        query = query.where(RequestLog.user_id == user_id)
    if api_key_id is not None:
        query = query.where(RequestLog.api_key_id == api_key_id)
    return int(await session.scalar(query) or 0)
