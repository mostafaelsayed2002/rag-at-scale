"""The answer cache, because every identical question costs money.

One check, at the top of /chat: if the same question has been answered in the
last hour, the stored answer is returned and nothing else runs — no embedding
call, no search, no generation.

Redis rather than a dictionary for three reasons: it survives a restart, every
worker and container shares it, and it expires its own entries instead of
growing forever.

Nothing here may break a request. Redis is an optimisation, so every call is
wrapped: if it is down or slow, the caller misses and does the real work,
exactly as if nothing had been stored.
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
    """Question in, answer out, with a time to live on every entry."""

    def __init__(self, client: Redis, ttl: int = 3600):
        self.client = client
        self.ttl = ttl
        # Reported by /metrics; also the honest way to tell whether the cache
        # is earning its keep.
        self.hits = 0
        self.misses = 0

    def _key(self, question: str) -> str:
        """Hash it: questions are long, arbitrary, and may repeat exactly."""
        return f"rag:{VERSION}:answer:{hashlib.sha256(question.encode()).hexdigest()}"

    async def get(self, question: str) -> str | None:
        try:
            found = await self.client.get(self._key(question))
        except RedisError as exc:
            logger.warning("cache read failed, continuing without it: %s", exc)
            return None
        if found is None:
            self.misses += 1
            return None
        self.hits += 1
        return found

    async def set(self, question: str, answer: str) -> None:
        try:
            # ex is the expiry in seconds, applied by Redis itself: the entry
            # disappears on its own, so nothing has to sweep up after it.
            await self.client.set(self._key(question), answer, ex=self.ttl)
        except RedisError as exc:
            logger.warning("cache write failed, continuing without it: %s", exc)


def build_cache() -> Cache:
    """Created once at startup. Connecting is lazy, so this never blocks.

    decode_responses returns str instead of bytes, which keeps callers from
    having to decode every value they read back.
    """
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("answer cache enabled, entries live for %ds", settings.cache_ttl)
    return Cache(client, ttl=settings.cache_ttl)
