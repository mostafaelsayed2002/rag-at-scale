"""Answer cache in Redis: a repeated question skips embedding, search and the LLM.

Redis is shared by all workers, survives restarts and expires old entries.
If Redis fails, the request just runs normally, as a cache miss.
"""

import hashlib
import logging

from redis.asyncio import Redis
from redis.exceptions import RedisError

from ..core.config import settings

logger = logging.getLogger(__name__)


# v2: the corpus moved to all EU acts in force with bge-base embeddings;
# answers cached from the old corpus must not be served.
VERSION = "v2"


class Cache:
    """Question in, answer out, with a time to live on every entry."""

    def __init__(self, client: Redis, ttl: int = 3600):
        self.client = client
        self.ttl = ttl
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
