"""All dashboard API routes, mounted under /app/api with CSRF protection."""

from fastapi import APIRouter, Depends

from app.portal import catalog, keys, leaderboard, ledger, me, usage
from app.portal.admin import audit, balances, health, models, settings, users
from app.portal.admin import usage as admin_usage
from app.portal.deps import csrf_protect

router = APIRouter(prefix="/app/api", dependencies=[Depends(csrf_protect)])
for member_router in (
    me.router,
    keys.router,
    catalog.router,
    ledger.router,
    usage.router,
    leaderboard.router,
):
    router.include_router(member_router)

# Every admin route also depends on AdminUser itself; the prefix is only for grouping.
for admin_router in (
    balances.router,
    users.router,
    admin_usage.router,
    models.router,
    settings.router,
    audit.router,
    health.router,
):
    router.include_router(admin_router, prefix="/admin")
