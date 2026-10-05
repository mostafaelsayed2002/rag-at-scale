"""Embed search queries with the same model the corpus was embedded with."""

import asyncio

import numpy as np
from langsmith import traceable
from sentence_transformers import SentenceTransformer

from ..core.config import settings


def build_embedder() -> SentenceTransformer:
    """Loaded once at startup (~0.5 GB); loading per request would add seconds."""
    from transformers.utils import logging as transformers_logging

    transformers_logging.disable_progress_bar()  # its "Loading weights" bar clutters startup logs
    model = SentenceTransformer(settings.embedding_model, device=settings.embedding_device)
    _encode(model, "warm up")  # the first call is slow; pay it at startup, not on a user
    return model


def _encode(model: SentenceTransformer, text: str) -> np.ndarray:
    return model.encode(
        settings.query_prefix + text, normalize_embeddings=True, show_progress_bar=False
    )


# Traced without the model object or the 768-number vector: both are noise.
@traceable(
    run_type="embedding",
    name="embed",
    process_inputs=lambda inputs: {"text": inputs.get("text")},
    process_outputs=lambda _: {"dims": settings.embedding_dim},
)
async def embed_vector(model: SentenceTransformer, text: str) -> np.ndarray:
    """Embed one question. Normalised to length 1, like the corpus, so cosine
    similarity is a plain dot product."""
    # A CPU-bound call: in a thread, so other requests keep being served.
    vector = await asyncio.to_thread(_encode, model, text)
    if vector.shape != (settings.embedding_dim,):
        raise ValueError(f"expected {settings.embedding_dim} dimensions, got {vector.shape}")
    return vector


def to_halfvec(vector: np.ndarray) -> str:
    """The vector as a pgvector halfvec literal, for the search query."""
    return "[" + ",".join(f"{value:.5f}" for value in vector) + "]"


async def embed_query(model: SentenceTransformer, text: str) -> str:
    """Embed one question and render it as a halfvec literal."""
    return to_halfvec(await embed_vector(model, text))
