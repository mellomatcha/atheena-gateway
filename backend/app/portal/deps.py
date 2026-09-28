"""Request dependencies for the dashboard API: session, current user, admin role, CSRF."""

import logging
from collections.abc import AsyncIterator
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.models import User
from app.portal.access import AccessDeniedError, AccessVerifier

logger = logging.getLogger(__name__)

CSRF_HEADER = "x-atheena-csrf"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class PortalError(Exception):
    """An error returned by the dashboard API as {"error": {"code", "message"}}."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={"error": {"code": self.code, "message": self.message}},
        )


def not_authenticated() -> PortalError:
    return PortalError(401, "not_authenticated", "Sesi tidak valid. Masuk ulang lewat portal.")


def account_inactive() -> PortalError:
    return PortalError(403, "account_inactive", "Akun belum aktif, hubungi admin.")


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def authenticated_email(request: Request) -> str:
    """The Cloudflare Access identity of this request (FR-1.1, FR-1.2)."""
    settings: Settings = request.app.state.settings
    bypass = settings.dev_auth_bypass_email
    if bypass is not None:
        return bypass
    verifier: AccessVerifier | None = request.app.state.access_verifier
    token = request.headers.get("cf-access-jwt-assertion") or request.cookies.get(
        "CF_Authorization"
    )
    if verifier is None or not token:
        raise not_authenticated()
    try:
        email = await verifier.verify(token)
    except AccessDeniedError as exc:
        logger.info("access token rejected", extra={"reason": str(exc)})
        raise not_authenticated() from exc
    header_email = request.headers.get("cf-access-authenticated-user-email")
    if header_email is not None and header_email.strip().lower() != email:
        logger.info("access token rejected", extra={"reason": "email header mismatch"})
        raise not_authenticated()
    return email


async def current_user(
    session: SessionDep, email: Annotated[str, Depends(authenticated_email)]
) -> User:
    """Passing Access is not enough: the email must be an active portal user (FR-1.3)."""
    user = await session.scalar(select(User).where(User.email == email))
    if user is None or user.status != "active":
        raise account_inactive()
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def require_admin(user: CurrentUser) -> User:
    """Role is checked on the server for every admin endpoint (§11)."""
    if user.role != "admin":
        raise PortalError(403, "admin_only", "Hanya admin yang boleh mengakses ini.")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


async def csrf_protect(request: Request) -> None:
    """Mutating requests must carry X-Atheena-CSRF: 1 and, if present, a same-host Origin.

    Browsers only send a custom header cross-origin after a CORS preflight, which the portal
    never approves, so a forged form or fetch from another site cannot pass this check.
    """
    if request.method not in UNSAFE_METHODS:
        return
    if request.headers.get(CSRF_HEADER) != "1":
        raise PortalError(403, "csrf_failed", "Permintaan ditolak (CSRF).")
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).netloc != request.headers.get("host"):
        raise PortalError(403, "csrf_failed", "Permintaan ditolak (CSRF).")
