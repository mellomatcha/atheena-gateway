"""Which catalog models a user or key may use (FR-3.4, FR-4.4, PRD §15 Q2)."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AIModel


def tier_allows(user_tier: str, min_tier: str) -> bool:
    return user_tier == "advanced" or min_tier == "basic"


async def allowed_models(
    session: AsyncSession, user_tier: str, allowlist: Sequence[str] | None = None
) -> list[AIModel]:
    """Active models allowed for the tier, narrowed by a key allowlist when given."""
    models = (
        await session.scalars(
            select(AIModel).where(AIModel.is_active.is_(True)).order_by(AIModel.public_name)
        )
    ).all()
    return [
        model
        for model in models
        if tier_allows(user_tier, model.min_tier)
        and (allowlist is None or model.public_name in allowlist)
    ]
