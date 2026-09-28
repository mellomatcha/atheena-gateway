import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    SmallInteger,
    Text,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin


def _token_column() -> Mapped[int]:
    return mapped_column(BigInteger, server_default=text("0"))


class RequestLog(IdMixin, TimestampMixin, Base):
    """One row per proxied request: metadata only, never prompt or response content.

    Range-partitioned by month on started_at. Postgres requires the partition key in every
    unique constraint, hence the composite primary key (id, started_at). For the same reason
    ledger_entries.request_id cannot carry a foreign key to this table.
    """

    __tablename__ = "requests"
    __table_args__ = (
        PrimaryKeyConstraint("id", "started_at"),
        Index(None, "user_id", "started_at"),
        Index(None, "model_id", "started_at"),
        Index(None, "project", "started_at"),
        Index("uq_requests_request_id_started_at", "request_id", "started_at", unique=True),
        {"postgresql_partition_by": "RANGE (started_at)"},
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    # Public id returned to the client as X-Request-Id (FR-3.17).
    request_id: Mapped[uuid.UUID]
    # Nullable: requests rejected with 401 have no identified user or key (FR-3.22).
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    api_key_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("api_keys.id"))
    # Nullable: requests for unknown models are logged with the requested name only.
    model_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("models.id"))
    model_public_name: Mapped[str | None] = mapped_column(Text)
    project: Mapped[str | None] = mapped_column(Text)
    endpoint: Mapped[str] = mapped_column(Text)
    is_stream: Mapped[bool] = mapped_column(server_default=false())
    status_code: Mapped[int] = mapped_column(SmallInteger)
    error_type: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int] = _token_column()
    output_tokens: Mapped[int] = _token_column()
    cache_write_tokens: Mapped[int] = _token_column()
    cache_read_tokens: Mapped[int] = _token_column()
    usage_estimated: Mapped[bool] = mapped_column(server_default=false())
    # The four model prices in effect when the request was billed (PRD §4.3.5).
    price_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    cost_idr: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    ttft_ms: Mapped[int | None] = mapped_column(Integer)
    client_ip_hash: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageDaily(IdMixin, TimestampMixin, Base):
    """Daily rollup of requests, filled by the scheduled worker job (PRD §7)."""

    __tablename__ = "usage_daily"
    __table_args__ = (
        Index(
            "uq_usage_daily_day_user_model_project",
            "day",
            "user_id",
            "model_id",
            "project",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    day: Mapped[date] = mapped_column(Date)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    model_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("models.id"))
    project: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int] = _token_column()
    output_tokens: Mapped[int] = _token_column()
    cache_write_tokens: Mapped[int] = _token_column()
    cache_read_tokens: Mapped[int] = _token_column()
    cost_idr: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    request_count: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
