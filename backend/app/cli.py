"""Admin command line (`make create-key EMAIL=... NAME=...`) until the dashboard exists."""

import argparse
import asyncio
import sys

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.config import get_settings
from app.db import create_sessionmaker
from app.gateway.keys import display_prefix, generate_key, hash_key
from app.gateway.settings_store import load_settings
from app.ids import new_id
from app.models import ApiKey, User


class CliError(Exception):
    pass


async def create_key(session: AsyncSession, email: str, name: str) -> str:
    """Create an API key for an existing user and return the plaintext key (shown once)."""
    user = await session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        raise CliError(f"user {email} not found")
    if not name.strip():
        raise CliError("key name must not be empty")
    active = await session.scalar(
        select(func.count()).where(ApiKey.user_id == user.id, ApiKey.status == "active")
    )
    limit = int((await load_settings(session))["max_active_keys_per_user"])
    if (active or 0) >= limit:
        raise CliError(f"user already has {limit} active keys (FR-2.5)")
    key = generate_key()
    session.add(
        ApiKey(
            id=new_id(),
            user_id=user.id,
            name=name.strip(),
            key_hash=hash_key(key),
            key_prefix=display_prefix(key),
        )
    )
    return key


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
