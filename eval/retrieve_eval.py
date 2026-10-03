"""Retrieval score on the golden set: Hit@k and MRR (Mean Reciprocal Rank). No LLM, so it costs nothing.

Runs the API's own embedder and retriever, so it measures exactly what the app
does. A question counts as a hit when any of its answer chunks is among the
top k results.

    uv run --project api python eval/retrieve_eval.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))


from langsmith import tracing_context
from tqdm import tqdm


from app.core.config import settings
from app.db.pool import pool
from app.rag.embedder import build_embedder, embed_query
from app.rag.reranker import build_reranker, rerank
from app.rag.retriever import retrieve

GOLDEN = ROOT / "eval" / "golden.jsonl"
K = settings.retrieve_k  # passages the app sends to the model


def load_golden() -> list[dict]:
    """The golden questions that have an answer. The 10 without one are
    skipped: there is no correct chunk to find."""
    questions = []
    with GOLDEN.open() as f:
        for line in f:
            question = json.loads(line)
            if question["answerable"]:
                questions.append(question)
    return questions


def first_rank(retrieved: list, wanted: list) -> int | None:
    """Position (1 = top) of the first retrieved chunk that is a correct one.

    None when no correct chunk was retrieved.
    """
    for position, chunk_id in enumerate(retrieved, start=1):
        if chunk_id in wanted:
            return position
    return None


async def main() -> None:
    """Search every golden question, then print Hit@K and MRR@K.

    Hit@K: share of questions with a correct chunk in the top K.
    MRR@K: average of 1/rank of the first correct chunk (1st = 1, 2nd = 0.5, ...),
    0 when none is found, so it also rewards putting the right chunk first.
    """
    golden = load_golden()
    await pool.open()
    print("loading the embedder...")
    model = build_embedder()
    print(f"loading the reranker ({settings.rerank_model})...")
    reranker = build_reranker()
    print(f"searching: top {settings.rerank_candidates} candidates, reranked to {K}")

    hits = 0
    reciprocal_ranks = 0.0
    rerank_seconds = 0.0
    # Kept out of LangSmith: 100 eval runs would bury the real traces.
    with tracing_context(enabled=False):
        for question in tqdm(golden, desc="questions"):
            vector = await embed_query(model, question["question"])
            # Same steps as the app: fetch the candidates, keep the best K.
            candidates = await retrieve(vector, settings.rerank_candidates)
            start = time.perf_counter()
            results = await rerank(reranker, question["question"], candidates, K)
            rerank_seconds += time.perf_counter() - start
            retrieved = [result["chunk_id"] for result in results]

            rank = first_rank(retrieved, question["chunk_ids"])
            if rank is not None:
                hits += 1
                reciprocal_ranks += 1 / rank
    await pool.close()

    print(f"{len(golden)} questions, top {K}")
    print(f"Hit@{K}: {hits / len(golden):.2f}")
    print(f"MRR@{K}: {reciprocal_ranks / len(golden):.2f}")
    print(f"rerank: {rerank_seconds / len(golden) * 1000:.0f} ms per question")


if __name__ == "__main__":
    asyncio.run(main())
