"""Mini exam for embedding models, before re-embedding the whole corpus.

For each golden question, take a pile of ~100 chunks: the current search's
top 100 plus the correct chunks. Each model sorts every pile by similarity to
the question; the score is how often a correct chunk lands in the top 6.
About 10 000 chunks instead of 1 million, so it runs in minutes.

The piles come from the current model's search, so this ranks the models
against each other; it is not the Hit@6 they would get on the full corpus.

    uv run --project api python eval/model_compare.py

The scoring part needs only sentence-transformers, so it also runs on a
Kaggle GPU with the piles file uploaded:

    python model_compare.py --piles /kaggle/input/<dataset>/piles.json
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

GOLDEN = ROOT / "eval" / "golden.jsonl"
PILES = ROOT / "eval" / "results" / "piles.json"
PILE_SIZE = 100
K = 6

# Each model with the prefixes it was trained with: (question prefix, chunk prefix).
MODELS = {
    "BAAI/bge-base-en-v1.5": ("Represent this sentence for searching relevant passages: ", ""),
    "BAAI/bge-large-en-v1.5": ("Represent this sentence for searching relevant passages: ", ""),
    "intfloat/e5-large-v2": ("query: ", "passage: "),
    "BAAI/bge-m3": ("", ""),
}

# A legal-specific model, through Voyage AI's paid API ($0.12 per 1M tokens;
# the piles are ~2.8M tokens). Voyage adds its own query/document prompts.
VOYAGE_MODEL = "voyage-law-2"
VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
VOYAGE_CACHE = ROOT / "eval" / "results" / "voyage-law-2-chunks.npy"


async def build_piles() -> list[dict]:
    """The pile of chunks for every answerable golden question, saved to a file
    so the models can be compared again without the database."""
    # Imported here: only this step needs the app and its database, so the
    # rest of the script runs anywhere (Kaggle) without them.
    from langsmith import tracing_context

    from app.db.pool import pool
    from app.rag.embedder import build_embedder, embed_query
    from app.rag.retriever import retrieve

    questions = []
    with GOLDEN.open() as f:
        for line in f:
            question = json.loads(line)
            if question["answerable"]:
                questions.append(question)

    await pool.open()
    embedder = build_embedder()
    piles = []
    with tracing_context(enabled=False):
        for q in tqdm(questions, desc="piles"):
            vector = await embed_query(embedder, q["question"])
            found = await retrieve(vector, PILE_SIZE)
            chunks = {}
            for chunk in found:
                chunks[chunk["chunk_id"]] = chunk["text"]
            # The correct chunks join the pile even when the search missed them.
            async with pool.connection() as conn:
                cur = await conn.execute(
                    "SELECT id, text FROM chunks WHERE id = ANY(%s)", (q["chunk_ids"],)
                )
                for row in await cur.fetchall():
                    chunks[row["id"]] = row["text"]
            piles.append(
                {
                    "id": q["id"],
                    "question": q["question"],
                    "gold": q["chunk_ids"],
                    "chunks": chunks,
                }
            )
    await pool.close()

    PILES.parent.mkdir(exist_ok=True)
    PILES.write_text(json.dumps(piles))
    return piles


def load_piles(path: Path) -> list[dict]:
    """The saved piles; JSON turns the chunk ids into strings, so turn them back."""
    piles = json.loads(path.read_text())
    for pile in piles:
        chunks = {}
        for chunk_id, text in pile["chunks"].items():
            chunks[int(chunk_id)] = text
        pile["chunks"] = chunks
    return piles


def distinct_chunks(piles: list[dict]) -> tuple[list[int], list[str]]:
    """Every chunk once, even when it sits in several piles: ids and texts."""
    ids = []
    texts = []
    seen = set()
    for pile in piles:
        for chunk_id, text in pile["chunks"].items():
            if chunk_id not in seen:
                seen.add(chunk_id)
                ids.append(chunk_id)
                texts.append(text)
    return ids, texts


def hit_and_mrr(piles: list[dict], vector_of: dict, question_vectors: list) -> tuple[float, float]:
    """Sort each pile by similarity to its question and score the top K."""
    hits = 0
    reciprocal_ranks = 0.0
    for pile, question in zip(piles, question_vectors):
        ids = list(pile["chunks"])
        scores = np.array([vector_of[chunk_id] @ question for chunk_id in ids])
        ranked = [ids[i] for i in np.argsort(-scores)]
        for position, chunk_id in enumerate(ranked[:K], start=1):
            if chunk_id in pile["gold"]:
                hits += 1
                reciprocal_ranks += 1 / position
                break
    return hits / len(piles), reciprocal_ranks / len(piles)


def score_model(name: str, piles: list[dict]) -> tuple[float, float, float]:
    """Hit@6 and MRR@6 of one local model over all piles, and the seconds it took."""
    question_prefix, chunk_prefix = MODELS[name]
    print("loading the model (downloaded the first time)...")
    model = SentenceTransformer(name)
    model.max_seq_length = 512  # the same text length for every model
    started = time.perf_counter()

    ids, texts = distinct_chunks(piles)
    texts = [chunk_prefix + text for text in texts]
    vectors = model.encode(texts, batch_size=16, normalize_embeddings=True, show_progress_bar=True)
    vector_of = dict(zip(ids, vectors))

    question_vectors = []
    for pile in tqdm(piles, desc="questions"):
        question_vectors.append(
            model.encode(question_prefix + pile["question"], normalize_embeddings=True)
        )

    hit, mrr = hit_and_mrr(piles, vector_of, question_vectors)
    return hit, mrr, time.perf_counter() - started


def voyage_embed(texts: list[str], input_type: str) -> np.ndarray:
    """Embed texts with Voyage's API, 64 per request, waiting and retrying when
    rate-limited. Needs VOYAGE_API_KEY in the environment or the .env file."""
    import httpx
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    headers = {"Authorization": f"Bearer {os.environ['VOYAGE_API_KEY']}"}
    vectors = []
    with tqdm(total=len(texts), desc=f"voyage {input_type}s") as bar:
        for start in range(0, len(texts), 64):
            batch = texts[start : start + 64]
            body = {"input": batch, "model": VOYAGE_MODEL, "input_type": input_type}
            while True:
                response = httpx.post(VOYAGE_URL, json=body, headers=headers, timeout=120)
                if response.status_code != 429:  # 429 means "too many requests"
                    break
                bar.write(f"rate-limited, retrying in 20 s: {response.text[:200]}")
                time.sleep(20)
            response.raise_for_status()
            for item in response.json()["data"]:
                vectors.append(item["embedding"])
            bar.update(len(batch))
    return np.array(vectors, dtype=np.float32)  # Voyage vectors are already length 1


def score_voyage(piles: list[dict]) -> tuple[float, float, float]:
    """Hit@6 and MRR@6 of voyage-law-2. The chunk vectors are saved after the
    first run, so running it again does not pay for them twice."""
    started = time.perf_counter()
    ids, texts = distinct_chunks(piles)
    if VOYAGE_CACHE.exists():
        vectors = np.load(VOYAGE_CACHE)
    else:
        vectors = voyage_embed(texts, "document")
        np.save(VOYAGE_CACHE, vectors)
    vector_of = dict(zip(ids, vectors))

    questions = [pile["question"] for pile in piles]
    question_vectors = voyage_embed(questions, "query")

    hit, mrr = hit_and_mrr(piles, vector_of, question_vectors)
    return hit, mrr, time.perf_counter() - started


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--piles", type=Path, default=PILES, help="the saved piles file")
    parser.add_argument(
        "--models", nargs="+", default=list(MODELS), help=f"which models; {VOYAGE_MODEL} uses the API"
    )
    args = parser.parse_args()

    if args.piles.exists():
        piles = load_piles(args.piles)
    else:
        print("building the piles (one search per question)...")
        piles = asyncio.run(build_piles())
    sizes = [len(pile["chunks"]) for pile in piles]
    print(f"{len(piles)} questions, {sum(sizes)} chunks in the piles\n")

    for name in args.models:
        print(f"--- {name}")
        if name == VOYAGE_MODEL:
            hit, mrr, seconds = score_voyage(piles)
        else:
            hit, mrr, seconds = score_model(name, piles)
        print(f"Hit@{K}: {hit:.2f}   MRR@{K}: {mrr:.2f}   ({seconds:.0f} s)\n")


if __name__ == "__main__":
    main()
