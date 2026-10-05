"""Retrieval score on the golden set: Hit@k and MRR (Mean Reciprocal Rank). No LLM, so it costs nothing.

Runs the API's own embedder, retriever and reranker, so it measures exactly what
the app does. Reports two things:

    vector search only:   Hit@6/10/20/50 and MRR@6 of the top 50
    vector + reranker:    Hit@6 and MRR@6 of the 6 chunks the app sends to the model

A retrieved chunk counts as correct when it comes from a gold act and contains a
real piece of the gold text: at least GOLD_SPAN letters and digits in a row,
ignoring spaces and punctuation. Text, not chunk ids, because re-chunking gives
every chunk a new id. The gold texts (eval/gold_texts.json) are the passages the
golden answers were verified against. Each chunk's first line is its header
("act | chapter | article"), which is left out of the match.

    uv run --project api python eval/retrieve_eval.py
"""

import asyncio
import json
import re
import sys
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
GOLD_TEXTS = ROOT / "eval" / "gold_texts.json"
K = settings.retrieve_k  # passages the app sends to the model
DEPTHS = (6, 10, 20, 50)
GOLD_SPAN = 120  # letters/digits in a row shared with the gold text


def load_golden() -> list[dict]:
    """The golden questions that have an answer, with their gold texts. The 10
    without one are skipped: there is nothing correct to find."""
    texts = json.loads(GOLD_TEXTS.read_text())
    questions = []
    with GOLDEN.open() as f:
        for line in f:
            question = json.loads(line)
            if question["answerable"]:
                question["texts"] = texts[question["id"]]
                questions.append(question)
    return questions


def letters(text: str) -> str:
    """Lowercase letters and digits only."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def gold_spans(texts: list[str]) -> set[str]:
    """Every GOLD_SPAN-long run of the gold text."""
    spans = set()
    for text in texts:
        t = letters(text)
        for i in range(len(t) - GOLD_SPAN + 1):
            spans.add(t[i : i + GOLD_SPAN])
    return spans


def is_correct(chunk: dict, question: dict, spans: set[str]) -> bool:
    """From a gold act and sharing a GOLD_SPAN-long run with the gold text."""
    if chunk["doc_id"] not in question["doc_ids"]:
        return False
    body = chunk["text"].split("\n", 1)[-1]  # without the header line
    t = letters(body)
    for i in range(len(t) - GOLD_SPAN + 1):
        if t[i : i + GOLD_SPAN] in spans:
            return True
    return False


def first_rank(chunks: list[dict], question: dict, spans: set[str]) -> int | None:
    """Position (1 = top) of the first correct chunk, or None."""
    for position, chunk in enumerate(chunks, start=1):
        if is_correct(chunk, question, spans):
            return position
    return None


def report(title: str, ranks: list, depths: tuple) -> None:
    """Hit@k for each depth and MRR@K, over all questions given."""
    n = len(ranks)
    hits = "  ".join(f"Hit@{k}: {sum(1 for r in ranks if r and r <= k) / n:.2f}" for k in depths)
    mrr = sum(1 / r for r in ranks if r and r <= K) / n
    print(f"  {title:22} {hits}   MRR@{K}: {mrr:.2f}")


async def main() -> None:
    """Search every golden question and print the scores."""
    golden = load_golden()
    await pool.open()
    print("loading the embedder and the reranker...")
    embedder = build_embedder()
    reranker = build_reranker()

    vector_ranks = []
    reranked_ranks = []
    # Kept out of LangSmith: 100 eval runs would bury the real traces.
    with tracing_context(enabled=False):
        for question in tqdm(golden, desc="questions"):
            spans = gold_spans(question["texts"])
            vector = await embed_query(embedder, question["question"])
            found = await retrieve(vector, max(DEPTHS))
            vector_ranks.append(first_rank(found, question, spans))
            # The app's path: rerank the top candidates, keep the best K.
            candidates = found[: settings.rerank_candidates]
            final = await rerank(reranker, question["question"], candidates, K)
            reranked_ranks.append(first_rank(final, question, spans))

    # Acts without HTML are not in the corpus (the original REACH regulation is
    # PDF-only), so a question whose acts are all missing cannot be found.
    gold_docs = sorted({doc for q in golden for doc in q["doc_ids"]})
    async with pool.connection() as conn:
        cursor = await conn.execute("SELECT doc_id FROM documents WHERE doc_id = ANY(%s)", (gold_docs,))
        stored = {row["doc_id"] for row in await cursor.fetchall()}
    await pool.close()
    reachable = [any(doc in stored for doc in q["doc_ids"]) for q in golden]

    print(f"\nall {len(golden)} answerable questions:")
    report("vector search", vector_ranks, DEPTHS)
    report("vector + reranker", reranked_ranks, (K,))
    missing = [q["id"] for q, ok in zip(golden, reachable) if not ok]
    if missing:
        kept = sum(reachable)
        print(f"\nthe {kept} whose acts are in the corpus (left out: {', '.join(missing)}):")
        report("vector search", [r for r, ok in zip(vector_ranks, reachable) if ok], DEPTHS)
        report("vector + reranker", [r for r, ok in zip(reranked_ranks, reachable) if ok], (K,))


if __name__ == "__main__":
    asyncio.run(main())
