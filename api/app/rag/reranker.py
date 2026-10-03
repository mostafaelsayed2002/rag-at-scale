"""Re-sort the retrieved passages by how well each one answers the question."""

import asyncio

from langsmith import traceable
from sentence_transformers import CrossEncoder

from ..core.config import settings


def build_reranker() -> CrossEncoder:
    """Loaded once at startup (~1 GB), like the embedder."""
    # Each passage is cut to its first rerank_max_tokens tokens for scoring:
    # the cost grows with length, and the start of a chunk says most.
    model = CrossEncoder(
        settings.rerank_model,
        device=settings.embedding_device,
        max_length=settings.rerank_max_tokens,
    )
    model.predict([("warm up", "warm up")])  # the first call is slow; pay it at startup
    return model


def _score(model: CrossEncoder, query: str, chunks: list[dict]) -> list[float]:
    """One relevance score per passage; higher means a better answer."""
    pairs = []
    for chunk in chunks:
        pairs.append((query, chunk["text"]))
    return model.predict(pairs, show_progress_bar=False).tolist()


# Traced without the model object, which is noise.
@traceable(
    run_type="retriever",
    name="rerank",
    process_inputs=lambda inputs: {"query": inputs.get("query"), "k": inputs.get("k")},
)
async def rerank(model: CrossEncoder, query: str, chunks: list[dict], k: int) -> list[dict]:
    """The k passages the reranker scores highest, best first."""
    # A CPU-bound call: in a thread, so other requests keep being served.
    scores = await asyncio.to_thread(_score, model, query, chunks)
    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = score
    ranked = sorted(chunks, key=lambda chunk: chunk["rerank_score"], reverse=True)
    return ranked[:k]
