"""Embed search queries with the same model the corpus was embedded with."""

import numpy as np
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langsmith import traceable

from ..core.config import settings
from ..core.errors import QuotaExhausted, is_quota_error


def build_embedder() -> GoogleGenerativeAIEmbeddings:
    """Created once at startup; building it per request would add latency."""
    return GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        output_dimensionality=settings.embedding_dim,
        # Passed explicitly: pydantic-settings reads .env into the Settings
        # object, not into the process environment where the client looks.
        google_api_key=settings.google_api_key,
    )


# Traced without the client object or the 768-number vector: both are noise.
@traceable(
    run_type="embedding",
    name="embed",
    process_inputs=lambda inputs: {"text": inputs.get("text")},
    process_outputs=lambda _: {"dims": settings.embedding_dim},
)
def embed_query(embedder: GoogleGenerativeAIEmbeddings, text: str) -> str:
    """Embed one query and render it as a pgvector literal.

    Normalised to length 1, matching how the corpus was stored, so cosine
    distance and inner product agree.
    """
    try:
        raw = embedder.embed_query(text)
    except Exception as exc:
        if is_quota_error(exc):
            raise QuotaExhausted("embedding", str(exc)) from exc
        raise
    vector = np.asarray(raw, dtype=np.float32)
    if vector.shape != (settings.embedding_dim,):
        raise ValueError(f"expected {settings.embedding_dim} dimensions, got {vector.shape}")
    vector /= max(float(np.linalg.norm(vector)), 1e-12)
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"
