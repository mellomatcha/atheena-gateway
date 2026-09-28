import uuid
from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, TimestampMixin, check_in

LEDGER_TYPES = ("topup", "usage", "adjustment", "refund")
TOPUP_STATUSES = ("pending", "approved", "rejected")


class LedgerEntry(IdMixin, TimestampMixin, Base):
    """Append-only balance ledger (PRD §4.3.6).

    A database trigger rejects UPDATE, DELETE, and TRUNCATE; corrections are new entries.
    updated_at exists only for schema uniformity and always equals created_at.
    """

    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint(check_in("type", LEDGER_TYPES), name="type"),
        # Credits are positive, debits negative (FR-5.2).
        CheckConstraint(
            "(type NOT IN ('topup', 'refund') OR amount_idr > 0)"
            " AND (type <> 'usage' OR amount_idr <= 0)",
            name="amount_sign",
        ),
        CheckConstraint(
            "type <> 'adjustment' OR (note IS NOT NULL AND btrim(note) <> '')",
            name="adjustment_requires_note",
        ),
        Index(None, "user_id", "created_at"),
        Index(None, "request_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[str] = mapped_column(Text)
    amount_idr: Mapped[int] = mapped_column(BigInteger)
    balance_after_idr: Mapped[int] = mapped_column(BigInteger)
    # No foreign key: requests is partitioned and its unique keys include started_at.
    request_id: Mapped[uuid.UUID | None]
    topup_request_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("topup_requests.id"))
    note: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class TopupRequest(IdMixin, TimestampMixin, Base):
    """Top-up approval queue; unused in the MVP WhatsApp flow but created early (FR-5.4)."""

    __tablename__ = "topup_requests"
    __table_args__ = (
        CheckConstraint(check_in("status", TOPUP_STATUSES), name="status"),
        CheckConstraint("amount_requested_idr > 0", name="amount_requested_positive"),
        Index(None, "user_id", "created_at"),
        Index(None, "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    amount_requested_idr: Mapped[int] = mapped_column(BigInteger)
    amount_approved_idr: Mapped[int | None] = mapped_column(BigInteger)
    proof_path: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="pending")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
