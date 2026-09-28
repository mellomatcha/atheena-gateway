"""Audit trail of admin actions (FR-7.7, PRD §11 Operasional)."""

import uuid
from typing import Any

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.ids import new_id
from app.models import AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    actor_user_id: uuid.UUID | None,
    action: str,
    target_type: str,
    target_id: str | None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    ip_hash: str | None = None,
) -> None:
    await session.execute(
        insert(AuditLog).values(
            id=new_id(),
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
            ip_hash=ip_hash,
        )
    )
