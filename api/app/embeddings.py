"""Embed search queries with the same model the corpus was embedded with."""

import numpy as np
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from .config import settings


def build_embedder() -> GoogleGenerativeAIEmbeddings:
    """Created once at startup; building it per request would add latency."""
    if not settings.google_api_key:
        raise RuntimeError("Set GOOGLE_API_KEY to embed search queries")
    return GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        output_dimensionality=settings.embedding_dim,
        # Passed explicitly: pydantic-settings reads .env into the Settings
        # object, not into the process environment where the client looks.
        google_api_key=settings.google_api_key,
    )


def embed_query(embedder: GoogleGenerativeAIEmbeddings, text: str) -> str:
    """Embed one query and render it as a pgvector literal.

    Normalised to length 1, matching how the corpus was stored, so cosine
    distance and inner product agree.
    """
    vector = np.asarray(embedder.embed_query(text), dtype=np.float32)
    if vector.shape != (settings.embedding_dim,):
        raise ValueError(f"expected {settings.embedding_dim} dimensions, got {vector.shape}")
    vector /= max(float(np.linalg.norm(vector)), 1e-12)
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"
