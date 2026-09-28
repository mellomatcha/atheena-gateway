"""Rate limits and concurrent-stream limits kept in Redis (FR-3.7, FR-3.8).

All counters live in Redis so the limits hold across several portal replicas (PRD §4.3.1).
"""

import time
import uuid

from redis.asyncio import Redis

WINDOW_S = 60
# A stream slot whose holder has not refreshed it for this long is treated as leaked
# (for example a replica that crashed mid-stream) and reclaimed.
STREAM_SLOT_STALE_S = 120

# Fixed one-minute windows for key and user, counted atomically. Returns the seconds until the
# window resets when either limit is exceeded, otherwise 0.
_RATE_LIMIT_LUA = """
local key_count = redis.call('INCR', KEYS[1])
if key_count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[3]) end
local user_count = redis.call('INCR', KEYS[2])
if user_count == 1 then redis.call('EXPIRE', KEYS[2], ARGV[3]) end
if key_count > tonumber(ARGV[1]) or user_count > tonumber(ARGV[2]) then
  local ttl = math.max(redis.call('TTL', KEYS[1]), redis.call('TTL', KEYS[2]))
  if ttl < 1 then ttl = 1 end
  return ttl
end
return 0
"""

# Stream slots as a sorted set of request ids scored by last refresh time.
_ACQUIRE_STREAM_LUA = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1] - ARGV[3])
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[2]) then return 0 end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[3] * 2)
return 1
"""


async def check_rate_limit(
    redis: Redis,
    api_key_id: uuid.UUID,
    user_id: uuid.UUID,
    per_key_limit: int,
    per_user_limit: int,
) -> int:
    """Count one request; return 0 if allowed, else the Retry-After seconds."""
    window = int(time.time()) // WINDOW_S
    result = await redis.eval(
        _RATE_LIMIT_LUA,
        2,
        f"rl:key:{api_key_id}:{window}",
        f"rl:user:{user_id}:{window}",
        per_key_limit,
        per_user_limit,
        WINDOW_S,
    )
    return int(result)


def _streams_key(user_id: uuid.UUID) -> str:
    return f"streams:{user_id}"


async def acquire_stream_slot(
    redis: Redis, user_id: uuid.UUID, request_id: str, limit: int
) -> bool:
    result = await redis.eval(
        _ACQUIRE_STREAM_LUA,
        1,
        _streams_key(user_id),
        time.time(),
        limit,
        STREAM_SLOT_STALE_S,
        request_id,
    )
    return bool(result)


async def refresh_stream_slot(redis: Redis, user_id: uuid.UUID, request_id: str) -> None:
    await redis.zadd(_streams_key(user_id), {request_id: time.time()}, xx=True)


async def release_stream_slot(redis: Redis, user_id: uuid.UUID, request_id: str) -> None:
    await redis.zrem(_streams_key(user_id), request_id)


async def active_stream_count(redis: Redis, user_id: uuid.UUID) -> int:
    cutoff = time.time() - STREAM_SLOT_STALE_S
    return int(await redis.zcount(_streams_key(user_id), cutoff, "+inf"))
