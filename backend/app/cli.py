"""Admin command line (`make create-key EMAIL=... NAME=...`) until the dashboard exists."""

import argparse
import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import get_settings
from app.db import create_sessionmaker
from app.models import User
from app.services.api_keys import ApiKeyError, create_api_key


class CliError(Exception):
    pass


async def create_key(session: AsyncSession, email: str, name: str) -> str:
    """Create an API key for an existing user and return the plaintext key (shown once)."""
    user = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise CliError(f"user {email} not found")
    try:
        created = await create_api_key(session, user, name)
    except ApiKeyError as exc:
        raise CliError(exc.message) from exc
    return created.plaintext


async def _run(args: argparse.Namespace) -> int:
    engine = create_async_engine(get_settings().database_url)
    try:
        async with create_sessionmaker(engine)() as session, session.begin():
            key = await create_key(session, args.email, args.name)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()
    print("API key (shown once, store it now):")
    print(key)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-key", help="create an API key for a user")
    create.add_argument("--email", required=True)
    create.add_argument("--name", required=True)
    args = parser.parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
