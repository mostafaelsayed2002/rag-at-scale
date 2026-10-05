"""Answer cache in Redis, at two levels:

- exact: the same question again skips embedding, search and the LLM.
- semantic: a question worded almost the same (cosine similarity at least
  settings.semantic_cache_threshold) gets the stored answer of the earlier one.
  Skips search and the LLM, not the embedding.

For the semantic level every answered question's vector is kept in a Redis
hash, and a lookup compares the new vector with all of them in numpy. Brute
force is fine at a few thousand questions (a millisecond); far more would call
for a vector index (Redis Stack or pgvector).

Redis is shared by all workers, survives restarts and expires old entries.
If Redis fails, the request just runs normally, as a cache miss.
"""

import base64
import hashlib
import logging
import time

import numpy as np
from redis.asyncio import Redis
from redis.exceptions import RedisError

from ..core.config import settings

logger = logging.getLogger(__name__)


# v2: the corpus moved to all EU acts in force with bge-base embeddings;
# answers cached from the old corpus must not be served.
VERSION = "v2"


def _hash(text: str) -> str:
    """Hash it: questions are long, arbitrary, and may repeat exactly."""
    return hashlib.sha256(text.encode()).hexdigest()


def _pack(vector: np.ndarray) -> str:
    """A vector as text for Redis: 16-bit floats, base64. ~2 KB for 768."""
    return base64.b64encode(vector.astype(np.float16).tobytes()).decode()


def _unpack(text: str) -> np.ndarray:
    return np.frombuffer(base64.b64decode(text), dtype=np.float16).astype(np.float32)


class Cache:
    """Question in, answer out, with a time to live on every entry."""

    def __init__(self, client: Redis, ttl: int = 3600, threshold: float = 0.95, size: int = 2000):
        self.client = client
        self.ttl = ttl
        self.threshold = threshold
        self.size = size
        self.hits = 0
        self.misses = 0

    def _key(self, question: str) -> str:
        return f"rag:{VERSION}:answer:{_hash(question)}"

    def _semantic_keys(self, scope: str) -> tuple[str, str]:
        """The vectors (question hash -> vector) and their write times, per
        scope: answers made with other settings are not reused."""
        base = f"rag:{VERSION}:semantic:{_hash(scope)[:16]}"
        return f"{base}:vectors", f"{base}:times"

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

    async def similar(self, scope: str, vector: np.ndarray) -> tuple[str, float] | None:
        """The stored answer of the most similar earlier question, and the
        similarity, if it reaches the threshold."""
        vectors, _ = self._semantic_keys(scope)
        try:
            stored = await self.client.hgetall(vectors)
        except RedisError as exc:
            logger.warning("semantic cache read failed, continuing without it: %s", exc)
            return None
        if not stored:
            return None

        fields = list(stored)
        matrix = np.stack([_unpack(stored[field]) for field in fields])
        scores = matrix @ vector.astype(np.float32)  # all length 1: dot product = cosine
        best = int(np.argmax(scores))
        if scores[best] < self.threshold:
            return None
        try:
            # The question's own exact-cache entry; gone if it has expired.
            answer = await self.client.get(f"rag:{VERSION}:answer:{fields[best]}")
        except RedisError as exc:
            logger.warning("semantic cache read failed, continuing without it: %s", exc)
            return None
        if answer is None:
            return None
        return answer, float(scores[best])

    async def remember(self, scope: str, question: str, vector: np.ndarray) -> None:
        """Keep an answered question's vector for later semantic lookups. Its
        answer is the exact-cache entry stored with set()."""
        vectors, times = self._semantic_keys(scope)
        field = _hash(question)
        now = time.time()
        try:
            await self.client.hset(vectors, field, _pack(vector))
            await self.client.zadd(times, {field: now})
            # Forget questions whose answers have expired, and the oldest
            # ones beyond the size limit.
            old = await self.client.zrangebyscore(times, 0, now - self.ttl)
            extra = await self.client.zcard(times) - len(old) - self.size
            if extra > 0:
                old += await self.client.zrange(times, len(old), len(old) + extra - 1)
            if old:
                await self.client.hdel(vectors, *old)
                await self.client.zrem(times, *old)
        except RedisError as exc:
            logger.warning("semantic cache write failed, continuing without it: %s", exc)


def build_cache() -> Cache:
    """Created once at startup. Connecting is lazy, so this never blocks.

    decode_responses returns str instead of bytes, which keeps callers from
    having to decode every value they read back.
    """
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    logger.info("answer cache enabled, entries live for %ds", settings.cache_ttl)
    return Cache(
        client,
        ttl=settings.cache_ttl,
        threshold=settings.semantic_cache_threshold,
        size=settings.semantic_cache_size,
    )
