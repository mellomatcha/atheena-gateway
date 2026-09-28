"""All dashboard API routes, mounted under /app/api with CSRF protection."""

from fastapi import APIRouter, Depends

from app.portal import catalog, keys, ledger, me, usage
from app.portal.admin import balances
from app.portal.deps import csrf_protect

router = APIRouter(prefix="/app/api", dependencies=[Depends(csrf_protect)])
router.include_router(me.router)
router.include_router(keys.router)
router.include_router(catalog.router)
router.include_router(ledger.router)
router.include_router(usage.router)
router.include_router(balances.router, prefix="/admin")
