import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    false,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, check_in

USER_ROLES = ("member", "admin")
USER_TIERS = ("basic", "advanced")
USER_STATUSES = ("active", "suspended", "pending")
API_KEY_STATUSES = ("active", "revoked")


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(check_in("role", USER_ROLES), name="role"),
        CheckConstraint(check_in("tier", USER_TIERS), name="tier"),
        CheckConstraint(check_in("status", USER_STATUSES), name="status"),
        # Emails are compared case-insensitively; store them normalized.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    email: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, server_default="member")
    tier: Mapped[str] = mapped_column(Text, server_default="basic")
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    # Denormalized sum of ledger_entries, updated in the same transaction (FR-5.1).
    balance_idr: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    low_balance_threshold_idr: Mapped[int] = mapped_column(BigInteger, server_default=text("10000"))
    daily_cap_idr: Mapped[int | None] = mapped_column(BigInteger)
    leaderboard_opt_out: Mapped[bool] = mapped_column(server_default=false())


class ApiKey(IdMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        CheckConstraint(check_in("status", API_KEY_STATUSES), name="status"),
        CheckConstraint("char_length(key_hash) = 64", name="key_hash_sha256_hex"),
        CheckConstraint("char_length(key_prefix) = 12", name="key_prefix_length"),
        Index(None, "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(Text)
    # SHA-256 hex digest of the full key; the plaintext key is never stored (FR-2.3).
    key_hash: Mapped[str] = mapped_column(Text, unique=True)
    key_prefix: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="active")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daily_cap_idr: Mapped[int | None] = mapped_column(BigInteger)
    model_allowlist: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
