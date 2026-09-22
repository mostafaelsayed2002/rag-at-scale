"""Turn chunk text into vectors with the Gemini embedding API.

Embedding now happens over the network, so this stage owns the things that
implies: batching to keep the number of calls down, and retrying when Google
rate-limits or briefly fails.
"""

import logging
import random
import re
import time
from collections.abc import Iterable, Iterator, Sequence
from functools import lru_cache
from itertools import islice

import numpy as np
from config import settings
from google.genai.errors import ClientError
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from models import Chunk

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 8
TOO_MANY_REQUESTS = 429

# The free tier's quota counts texts, not calls: one request carrying 97
# chunks consumed nearly the whole allowance of 100 per minute. So the budget
# below is in texts, and a sliding one-minute window spends it.
TEXTS_PER_MINUTE = settings.embed_texts_per_minute

# A batch larger than the per-minute budget can never succeed, so cap it.
BATCH = min(settings.embed_batch, TEXTS_PER_MINUTE)
_window_started = 0.0
_window_spent = 0


def _throttle(count: int) -> None:
    """Wait if sending `count` more texts would exceed this minute's budget."""
    global _window_started, _window_spent

    now = time.monotonic()
    if now - _window_started >= 60:
        _window_started, _window_spent = now, 0

    # Nothing spent yet and the batch alone exceeds the budget: waiting cannot
    # help, so send it and let the retry handle a refusal. BATCH keeps this
    # from happening in practice.
    if _window_spent == 0 and count > TEXTS_PER_MINUTE:
        _window_spent += count
        return

    if _window_spent + count > TEXTS_PER_MINUTE:
        wait = 60 - (now - _window_started)
        if wait > 0:
            logger.info("quota budget reached, waiting %.0fs", wait)
            time.sleep(wait)
        _window_started, _window_spent = time.monotonic(), 0

    _window_spent += count


def _client_error(exc: BaseException) -> ClientError | None:
    """Find the underlying API error; LangChain wraps it in its own type."""
    seen = exc
    while seen is not None:
        if isinstance(seen, ClientError):
            return seen
        seen = seen.__cause__
    return None


class DailyQuotaExhausted(RuntimeError):
    """The free tier's per-day allowance is gone until it resets."""


def _is_permanent(exc: Exception) -> bool:
    """True for failures that waiting cannot fix.

    The client raises ClientError for every 4xx: a rejected key, an unknown
    model, a malformed request. Those should fail at once. The exception is
    429, a rate limit, which is exactly what backing off is for, unless the
    quota that ran out is the daily one.
    """
    error = _client_error(exc)
    if error is None:
        return False
    if getattr(error, "code", None) != TOO_MANY_REQUESTS:
        return True
    # A per-day quota still reports "please retry in 44s", which is wrong:
    # the window resets tomorrow, not in a minute.
    return "PerDay" in str(exc)


def _retry_after(exc: Exception) -> float | None:
    """The wait Google asks for, in seconds, when it reports a rate limit.

    Its own number beats guessing: it knows when the quota window resets.
    """
    match = re.search(r"[Pp]lease retry in ([\d.]+)s", str(exc))
    return float(match.group(1)) if match else None


@lru_cache(maxsize=1)
def _embedder() -> GoogleGenerativeAIEmbeddings:
    """Built on first use, once per process, so importing stays cheap."""
    if not settings.google_api_key:
        raise RuntimeError("Set GOOGLE_API_KEY in .env to embed with Gemini")
    return GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        output_dimensionality=settings.embedding_dim,
        # Passed explicitly: pydantic-settings reads .env into this object, not
        # into the process environment where the client looks for the key.
        google_api_key=settings.google_api_key,
    )


def _with_retries(call, what: str, count: int = 1):
    """Retry on rate limits and transient failures, backing off each time.

    Embedding a corpus is thousands of calls, so a single 429 or dropped
    connection should not end the run. Problems that waiting cannot fix, such
    as a missing or rejected key, are raised immediately.
    """
    _embedder()  # fails fast on a missing key, before any waiting

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            _throttle(count)
            return call()
        except Exception as exc:
            if _is_permanent(exc) and "PerDay" in str(exc):
                raise DailyQuotaExhausted(
                    "Gemini free tier daily quota is used up. Enable billing on "
                    "the project, or continue after it resets."
                ) from exc
            if attempt == MAX_ATTEMPTS or _is_permanent(exc):
                raise
            # Google says how long its quota window has left; otherwise back
            # off exponentially. Jitter keeps parallel workers out of step.
            wait = _retry_after(exc) or min(2**attempt, 30)
            wait += random.random()
            logger.warning("%s rate-limited or failed, retrying in %.0fs", what, wait)
            logger.debug("cause: %s", exc)
            time.sleep(wait)
    raise AssertionError("unreachable")


def _normalise(vectors: np.ndarray) -> np.ndarray:
    """Scale each vector to length 1, so cosine similarity is a dot product.

    Gemini normalises its full-size output itself, but shorter outputs are
    truncations that may not be, and pgvector's cheaper inner product operator
    only matches cosine on unit vectors.
    """
    lengths = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.maximum(lengths, 1e-12)


def embed_texts(texts: Sequence[str]) -> np.ndarray:
    """Embed passages. Returns float32 of shape (len(texts), settings.embedding_dim)."""
    if not texts:
        return np.empty((0, settings.embedding_dim), dtype=np.float32)

    vectors = _with_retries(
        lambda: _embedder().embed_documents(list(texts), batch_size=BATCH),
        f"embedding {len(texts)} texts",
        count=len(texts),
    )
    array = np.asarray(vectors, dtype=np.float32)
    if array.shape != (len(texts), settings.embedding_dim):
        raise ValueError(f"expected {len(texts)}x{settings.embedding_dim} vectors, got {array.shape}")
    return _normalise(array)


def embed_query(text: str) -> np.ndarray:
    """Embed one search query."""
    vector = _with_retries(lambda: _embedder().embed_query(text), "embedding a query")
    return _normalise(np.asarray([vector], dtype=np.float32))[0]


def embed_chunks(
    chunks: Iterable[Chunk], batch_size: int = BATCH
) -> Iterator[tuple[Chunk, np.ndarray]]:
    """Pair each chunk with its vector, one batch in memory at a time."""
    iterator = iter(chunks)
    while batch := list(islice(iterator, batch_size)):
        vectors = embed_texts([chunk.text for chunk in batch])
        yield from zip(batch, vectors)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    vectors = embed_texts(
        [
            "A personal data breach must be notified within 72 hours.",
            "The AI Act lists recruitment systems as high risk.",
        ]
    )
    query = embed_query("How fast do we report a breach?")
    print(f"vectors {vectors.shape} {vectors.dtype}, query {query.shape}")
    print("similarity to each passage:", (vectors @ query).round(3).tolist())
