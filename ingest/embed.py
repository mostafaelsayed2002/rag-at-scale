"""Turn chunk text into vectors with the Gemini embedding API.

Embedding now happens over the network, so this stage owns the things that
implies: batching to keep the number of calls down, and retrying when Google
rate-limits or briefly fails.
"""

import logging
import random
import time
from collections.abc import Iterable, Iterator, Sequence
from functools import lru_cache
from itertools import islice

import numpy as np
from config import EMBED_BATCH, EMBEDDING_DIM, EMBEDDING_MODEL, GOOGLE_API_KEY
from google.genai.errors import ClientError
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from models import Chunk

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5
TOO_MANY_REQUESTS = 429


def _is_permanent(exc: Exception) -> bool:
    """True for failures that waiting cannot fix.

    The client raises ClientError for every 4xx: a rejected key, an unknown
    model, a malformed request. Those should fail at once. The exception is
    429, a rate limit, which is exactly what backing off is for.
    """
    return isinstance(exc, ClientError) and getattr(exc, "code", None) != TOO_MANY_REQUESTS


@lru_cache(maxsize=1)
def _embedder() -> GoogleGenerativeAIEmbeddings:
    """Built on first use, once per process, so importing stays cheap."""
    if not GOOGLE_API_KEY:
        raise RuntimeError("Set GOOGLE_API_KEY in .env to embed with Gemini")
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        output_dimensionality=EMBEDDING_DIM,
    )


def _with_retries(call, what: str):
    """Retry on rate limits and transient failures, backing off each time.

    Embedding a corpus is thousands of calls, so a single 429 or dropped
    connection should not end the run. Problems that waiting cannot fix, such
    as a missing or rejected key, are raised immediately.
    """
    _embedder()  # fails fast on a missing key, before any waiting

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return call()
        except Exception as exc:
            if attempt == MAX_ATTEMPTS or _is_permanent(exc):
                raise
            # Random jitter, so parallel workers don't all retry in step.
            wait = min(2**attempt, 30) + random.random()
            logger.warning("%s failed (%s), retrying in %.1fs", what, exc, wait)
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
    """Embed passages. Returns float32 of shape (len(texts), EMBEDDING_DIM)."""
    if not texts:
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    vectors = _with_retries(
        lambda: _embedder().embed_documents(list(texts), batch_size=EMBED_BATCH),
        f"embedding {len(texts)} texts",
    )
    array = np.asarray(vectors, dtype=np.float32)
    if array.shape != (len(texts), EMBEDDING_DIM):
        raise ValueError(f"expected {len(texts)}x{EMBEDDING_DIM} vectors, got {array.shape}")
    return _normalise(array)


def embed_query(text: str) -> np.ndarray:
    """Embed one search query."""
    vector = _with_retries(lambda: _embedder().embed_query(text), "embedding a query")
    return _normalise(np.asarray([vector], dtype=np.float32))[0]


def embed_chunks(
    chunks: Iterable[Chunk], batch_size: int = EMBED_BATCH
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
