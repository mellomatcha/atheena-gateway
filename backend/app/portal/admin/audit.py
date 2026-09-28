"""Audit log viewer (FR-7.7)."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.models import AuditLog, User
from app.portal.deps import AdminUser, SessionDep

router = APIRouter()

PAGE_SIZE = 50


class AuditOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    actor_name: str | None
    actor_email: str | None
    action: str
    target_type: str
    target_id: str | None
    target_label: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None


class AuditPage(BaseModel):
    items: list[AuditOut]
    page: int
    page_size: int
    total: int
    actions: list[str]


@router.get("/audit-logs")
async def audit_logs(
    admin: AdminUser,
    session: SessionDep,
    page: int = Query(1, ge=1, le=100_000),
    action: str | None = Query(None, max_length=60),
) -> AuditPage:
    actor = aliased(User)
    target_user = aliased(User)
    conditions = [AuditLog.action == action] if action else []
    total = await session.scalar(select(func.count()).select_from(AuditLog).where(*conditions))
    rows = (
        await session.execute(
            select(
                AuditLog,
                actor.display_name.label("actor_name"),
                actor.email.label("actor_email"),
                target_user.display_name.label("target_user_name"),
            )
            .outerjoin(actor, actor.id == AuditLog.actor_user_id)
            .outerjoin(
                target_user,
                (AuditLog.target_type == "user")
                & (func.cast(target_user.id, AuditLog.target_id.type) == AuditLog.target_id),
            )
            .where(*conditions)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(PAGE_SIZE)
            .offset((page - 1) * PAGE_SIZE)
        )
    ).all()
    actions = (
        await session.scalars(
            select(AuditLog.action).group_by(AuditLog.action).order_by(AuditLog.action)
        )
    ).all()
    return AuditPage(
        items=[
            AuditOut(
                id=row.AuditLog.id,
                created_at=row.AuditLog.created_at,
                actor_name=row.actor_name,
                actor_email=row.actor_email,
                action=row.AuditLog.action,
                target_type=row.AuditLog.target_type,
                target_id=row.AuditLog.target_id,
                target_label=row.target_user_name,
                before=row.AuditLog.before,
                after=row.AuditLog.after,
            )
            for row in rows
        ],
        page=page,
        page_size=PAGE_SIZE,
        total=int(total or 0),
        actions=list(actions),
    )
