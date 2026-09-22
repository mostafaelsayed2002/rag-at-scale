"""A shared cache in Redis, because every identical query costs money.

A dictionary in the process would have worked for one server on one machine.
Redis is here for the three things it cannot do: survive a restart, be shared
by every worker and every container, and expire its own entries instead of
growing forever.

Nothing here is allowed to break a request. Redis is an optimisation, so every
call to it is wrapped: if it is down or slow, the caller misses the cache and
does the real work, exactly as if the entry had never been stored.
"""

import hashlib
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from .config import settings

logger = logging.getLogger(__name__)

# Bumped when the meaning of a stored value changes, so a new deployment
# ignores the old entries rather than serving something it would not produce
# today. Cheaper and safer than emptying the database by hand.
VERSION = "v1"


class Cache:
    """Key-value cache over Redis, with a time to live on every entry."""

    def __init__(self, client: Redis | None, ttl: int = 3600):
        self.client = client
        self.ttl = ttl
        # Counted for /metrics later; also the honest way to tell whether the
        # cache is earning its keep.
        self.hits = 0
        self.misses = 0

    def _key(self, namespace: str, value: str) -> str:
        """Hash the value: queries are long, arbitrary, and may repeat."""
        digest = hashlib.sha256(value.encode()).hexdigest()
        return f"rag:{VERSION}:{namespace}:{digest}"

    async def get(self, namespace: str, value: str) -> str | None:
        if self.client is None:
            return None
        try:
            found = await self.client.get(self._key(namespace, value))
        except RedisError as exc:
            logger.warning("cache read failed, continuing without it: %s", exc)
            return None
        if found is None:
            self.misses += 1
            return None
        self.hits += 1
        return found

    async def set(self, namespace: str, value: str, result: str) -> None:
        if self.client is None:
            return
        try:
            # ex is the expiry in seconds, applied by Redis itself: the entry
            # disappears on its own, so nothing has to sweep up after it.
            await self.client.set(self._key(namespace, value), result, ex=self.ttl)
        except RedisError as exc:
            logger.warning("cache write failed, continuing without it: %s", exc)


def build_cache() -> Cache:
    """Created once at startup. Connecting is lazy, so this never blocks.

    decode_responses returns str instead of bytes, which keeps callers from
    having to decode every value they read back.
    """
    if not settings.redis_url:
        logger.info("no REDIS_URL set; running without a cache")
        return Cache(None)
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("cache enabled, entries live for %ds", settings.cache_ttl)
    return Cache(client, ttl=settings.cache_ttl)
