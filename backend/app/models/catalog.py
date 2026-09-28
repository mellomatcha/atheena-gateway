from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, Integer, Numeric, Text, false, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, check_in
from app.models.users import USER_TIERS

API_FORMATS = ("openai", "anthropic", "both")
MODEL_CATEGORIES = ("official", "experimental")
PRICE_COLUMNS = (
    "price_input_per_m",
    "price_output_per_m",
    "price_cache_write_per_m",
    "price_cache_read_per_m",
)


def _price_column() -> Mapped[Decimal]:
    # Rupiah per 1M tokens; NUMERIC keeps fractional prices exact (PRD §7).
    return mapped_column(Numeric(14, 2), server_default=text("0"))


class AIModel(IdMixin, TimestampMixin, Base):
    __tablename__ = "models"
    __table_args__ = (
        CheckConstraint(check_in("api_format", API_FORMATS), name="api_format"),
        CheckConstraint(check_in("category", MODEL_CATEGORIES), name="category"),
        CheckConstraint(check_in("min_tier", USER_TIERS), name="min_tier"),
        CheckConstraint(
            " AND ".join(f"{column} >= 0" for column in PRICE_COLUMNS), name="prices_non_negative"
        ),
    )

    # Client-facing name without provider prefix (FR-4.0).
    public_name: Mapped[str] = mapped_column(Text, unique=True)
    # Admin-only: never exposed to members or clients (FR-4.0).
    upstream_id: Mapped[str] = mapped_column(Text)
    api_format: Mapped[str] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    min_tier: Mapped[str] = mapped_column(Text, server_default="basic")
    is_active: Mapped[bool] = mapped_column(server_default=false())
    context_window: Mapped[int | None] = mapped_column(Integer)
    price_input_per_m: Mapped[Decimal] = _price_column()
    price_output_per_m: Mapped[Decimal] = _price_column()
    price_cache_write_per_m: Mapped[Decimal] = _price_column()
    price_cache_read_per_m: Mapped[Decimal] = _price_column()


class Project(IdMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    # Reject experimental (non-official) models for this project (FR-3.10).
    official_only: Mapped[bool] = mapped_column(server_default=false())


class Setting(IdMixin, TimestampMixin, Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(Text, unique=True)
    value: Mapped[Any] = mapped_column(JSONB)
