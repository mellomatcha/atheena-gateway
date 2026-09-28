"""Models the member may use (§8: GET /models). Upstream ids and providers stay hidden."""

from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel

from app.portal.deps import CurrentUser, SessionDep
from app.services.catalog import allowed_models

router = APIRouter()


class ModelOut(BaseModel):
    """Member view of a catalog model; deliberately omits upstream_id and provider (FR-4.0)."""

    name: str
    api_format: str
    category: str
    min_tier: str
    context_window: int | None
    price_input_per_m: Decimal
    price_output_per_m: Decimal
    price_cache_write_per_m: Decimal
    price_cache_read_per_m: Decimal


@router.get("/models")
async def list_models(user: CurrentUser, session: SessionDep) -> list[ModelOut]:
    return [
        ModelOut(
            name=m.public_name,
            api_format=m.api_format,
            category=m.category,
            min_tier=m.min_tier,
            context_window=m.context_window,
            price_input_per_m=m.price_input_per_m,
            price_output_per_m=m.price_output_per_m,
            price_cache_write_per_m=m.price_cache_write_per_m,
            price_cache_read_per_m=m.price_cache_read_per_m,
        )
        for m in await allowed_models(session, user.tier)
    ]
