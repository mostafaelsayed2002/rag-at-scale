"""Re-sort the retrieved passages by how well each one answers the question."""

import asyncio
import logging

import httpx
from langsmith import traceable

from ..core.config import settings

log = logging.getLogger(__name__)

VOYAGE_URL = "https://api.voyageai.com/v1/rerank"
RETRIES = 3  # on 429 "too many requests"


def build_reranker() -> httpx.AsyncClient:
    """One client for the app's lifetime, so connections are reused."""
    return httpx.AsyncClient(
        headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
        timeout=30,
    )


async def _scores(client: httpx.AsyncClient, query: str, chunks: list[dict]) -> list[float]:
    """One relevance score per passage, from Voyage; higher means a better answer."""
    body = {
        "query": query,
        "documents": [chunk["text"] for chunk in chunks],
        "model": settings.rerank_model,
    }
    for attempt in range(RETRIES):
        response = await client.post(VOYAGE_URL, json=body)
        if response.status_code != 429 or attempt == RETRIES - 1:
            break
        await asyncio.sleep(2 ** attempt)
    response.raise_for_status()
    scores = [0.0] * len(chunks)
    for item in response.json()["data"]:
        scores[item["index"]] = item["relevance_score"]
    return scores


# Traced without the client object, which is noise.
@traceable(
    run_type="retriever",
    name="rerank",
    process_inputs=lambda inputs: {"query": inputs.get("query"), "k": inputs.get("k")},
)
async def rerank(client: httpx.AsyncClient, query: str, chunks: list[dict], k: int) -> list[dict]:
    """The k passages the reranker scores highest, best first.

    If Voyage cannot be reached, the vector search order is kept: a weaker
    answer beats no answer.
    """
    try:
        scores = await _scores(client, query, chunks)
    except httpx.HTTPError as error:
        log.warning("rerank failed, keeping the vector order: %s", error)
        return chunks[:k]
    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = score
    ranked = sorted(chunks, key=lambda chunk: chunk["rerank_score"], reverse=True)
    return ranked[:k]
