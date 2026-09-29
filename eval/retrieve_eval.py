"""Retrieval score on the golden set: Hit@k and MRR (Mean Reciprocal Rank). No LLM, so it costs nothing.

Runs the API's own embedder and retriever, so it measures exactly what the app
does. A question counts as a hit when any of its answer chunks is among the
top k results.

    uv run --project api python eval/retrieve_eval.py
"""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from langsmith import tracing_context

from app.core.config import settings
from app.db.pool import pool
from app.rag.embedder import build_embedder, embed_query
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
    model = build_embedder()

    hits = 0
    reciprocal_ranks = 0.0
    # Kept out of LangSmith: 100 eval
    with tracing_context(enabled=False):
        for question in golden:
            vector = await embed_query(model, question["question"])
            results = await retrieve(vector, K)
            retrieved = [result["chunk_id"] for result in results]

            rank = first_rank(retrieved, question["chunk_ids"])
            if rank is not None:
                hits += 1
                reciprocal_ranks += 1 / rank
    await pool.close()

    print(f"{len(golden)} questions, top {K}")
    print(f"Hit@{K}: {hits / len(golden):.2f}")
    print(f"MRR@{K}: {reciprocal_ranks / len(golden):.2f}")


if __name__ == "__main__":
    asyncio.run(main())
