"""Verify that Postgres and Redis from the current settings are reachable (`make dev`)."""

import asyncio
import sys

from redis.asyncio import Redis

from app.config import get_settings
from app.db import create_engine
from app.health import check_postgres, check_redis


async def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    redis = Redis.from_url(settings.redis_url)
    failed = False
    for name, check in (("postgres", check_postgres(engine)), ("redis", check_redis(redis))):
        try:
            await asyncio.wait_for(check, timeout=5)
        except Exception as exc:
            failed = True
            print(f"{name}: FAIL ({type(exc).__name__})", file=sys.stderr)
        else:
            print(f"{name}: ok")
    await redis.aclose()
    await engine.dispose()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
