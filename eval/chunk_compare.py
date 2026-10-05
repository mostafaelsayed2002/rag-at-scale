"""Does structure-based chunking find answers better than size-based chunking?

A fair test on a slice of the corpus: the ~3,000 acts that appear in the golden
questions' top-100 piles (the right acts plus realistic distractors). The same
acts are chunked two ways and embedded with the same model (bge-base):

    old: the chunks and vectors already in the database (by size, ~1,600 chars)
    new: ingest/structure.py (by article, with an "act | chapter | article" header)

Chunk ids differ between the two, so a retrieved chunk counts as correct when it
comes from a gold act and contains a real piece of the gold text: at least
GOLD_SPAN letters and digits in a row, ignoring spaces and punctuation.

Three steps:

    uv run --package rag-ingest python eval/chunk_compare.py prepare        # Mac: old + PDF chunks
    uv run --package rag-ingest python eval/chunk_compare.py prepare-html   # Mac: HTML chunks
    python chunk_compare.py embed --dir <input> --name html                 # Kaggle GPU
    uv run --package rag-ingest python eval/chunk_compare.py score          # Mac
"""

import argparse
import gzip
import json
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "eval" / "results" / "chunking"
PILES = ROOT / "eval" / "results" / "piles.json"
GOLDEN = ROOT / "eval" / "golden.jsonl"
PDF_DIR = ROOT / "data" / "eurlex" / "pdf"
HTML_DIR = ROOT / "data" / "eurlex" / "html"
ACTS = ROOT / "data" / "eurlex" / "acts.jsonl"

MODEL = "BAAI/bge-base-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
MAX_TOKENS = 480  # header included; the model reads at most 512
K = 6
GOLD_SPAN = 120  # letters/digits in a row shared with the gold text


# --- prepare ------------------------------------------------------------------


def chunk_one(job: tuple[str, str]) -> list[dict]:
    """Parse one PDF and chunk it by structure (runs in a worker process)."""
    sys.path.insert(0, str(ROOT / "ingest"))
    from chunk import count_tokens
    from structure import read_pages, structure_chunks

    doc_id, title = job
    path = PDF_DIR / f"{doc_id}.pdf"
    if not path.exists():
        return []

    def tokens(text: str) -> int:
        return count_tokens([text])[0]

    chunks = structure_chunks(title, read_pages(str(path)), tokens, MAX_TOKENS)
    for chunk in chunks:
        chunk["doc_id"] = doc_id
    return chunks


def prepare() -> None:
    """Pick the acts, export their old chunks and vectors, make the new chunks."""
    import psycopg
    from dotenv import dotenv_values

    OUT.mkdir(parents=True, exist_ok=True)
    database_url = dotenv_values(ROOT / ".env")["DATABASE_URL"]

    piles = json.loads(PILES.read_text())
    pile_ids = sorted({int(chunk_id) for pile in piles for chunk_id in pile["chunks"]})

    with psycopg.connect(database_url) as conn:
        doc_ids = [
            row[0]
            for row in conn.execute(
                "SELECT DISTINCT doc_id FROM chunks WHERE id = ANY(%s)", (pile_ids,)
            )
        ]
        print(f"{len(doc_ids)} acts in the test corpus")

        titles = {}
        for doc_id, title in conn.execute(
            "SELECT doc_id, title FROM documents WHERE doc_id = ANY(%s)", (doc_ids,)
        ):
            titles[doc_id] = title or ""

        # The gold text of every question, for scoring.
        golden = [json.loads(line) for line in GOLDEN.open()]
        gold = []
        for q in golden:
            if not q["answerable"]:
                continue
            texts = [
                row[0]
                for row in conn.execute("SELECT text FROM chunks WHERE id = ANY(%s)", (q["chunk_ids"],))
            ]
            gold.append({"id": q["id"], "question": q["question"], "doc_ids": q["doc_ids"], "texts": texts})
        (OUT / "gold.json").write_text(json.dumps(gold))

        # Old chunks and their vectors, straight from the database.
        old_chunks = []
        old_vectors = []
        cursor = conn.execute(
            "SELECT doc_id, text, embedding::text FROM chunks WHERE doc_id = ANY(%s) ORDER BY id",
            (doc_ids,),
        )
        for doc_id, text, embedding in tqdm(cursor, desc="old chunks", unit=" chunks"):
            old_chunks.append({"doc_id": doc_id, "text": text})
            old_vectors.append(np.array(embedding[1:-1].split(","), dtype=np.float16))
    with gzip.open(OUT / "old_chunks.jsonl.gz", "wt") as f:
        for chunk in old_chunks:
            f.write(json.dumps(chunk) + "\n")
    np.save(OUT / "old_vectors.npy", np.stack(old_vectors))
    print(f"old: {len(old_chunks)} chunks")

    # New chunks: parse every PDF again and chunk it by structure.
    new_chunks = []
    jobs = [(doc_id, titles.get(doc_id, "")) for doc_id in doc_ids]
    with ProcessPoolExecutor(max_workers=6) as pool:
        for chunks in tqdm(pool.map(chunk_one, jobs, chunksize=4), total=len(jobs), desc="new chunks"):
            new_chunks += chunks
    with gzip.open(OUT / "new_chunks.jsonl.gz", "wt") as f:
        for chunk in new_chunks:
            f.write(json.dumps(chunk) + "\n")
    print(f"new: {len(new_chunks)} chunks")


def read_chunks(folder: Path, name: str) -> list[dict]:
    """old_chunks / new_chunks from a folder. Kaggle unpacks .gz files on
    upload, into a plain file or a folder holding it, so accept all three."""
    path = folder / f"{name}_chunks.jsonl.gz"
    if path.is_file():
        with gzip.open(path, "rt") as f:
            return [json.loads(line) for line in f]
    plain = folder / f"{name}_chunks.jsonl"
    if plain.is_dir():
        plain = next(p for p in sorted(plain.iterdir()) if p.is_file())
    if not plain.is_file() and path.is_dir():
        plain = next(p for p in sorted(path.iterdir()) if p.is_file())
    with plain.open() as f:
        return [json.loads(line) for line in f]


def chunk_html_one(job: tuple[str, str]) -> list[dict] | None:
    """Chunk one act from its HTML (runs in a worker process); None if the
    act has no HTML."""
    sys.path.insert(0, str(ROOT / "ingest"))
    from chunk import count_tokens
    from html_chunk import html_chunks

    doc_id, title = job
    for suffix in ("xhtml", "html"):
        path = HTML_DIR / f"{doc_id}.{suffix}"
        if path.exists():

            def tokens(text: str) -> int:
                return count_tokens([text])[0]

            chunks = html_chunks(path.read_bytes(), title, tokens, MAX_TOKENS)
            for chunk in chunks:
                chunk["doc_id"] = doc_id
            return chunks
    return None


def prepare_html() -> None:
    """Chunk the same acts from their HTML. Acts without HTML keep their
    structure-based PDF chunks, as they would in the real corpus."""
    pdf_chunks = {}
    for chunk in read_chunks(OUT, "new"):
        pdf_chunks.setdefault(chunk["doc_id"], []).append(chunk)
    titles = {}
    with ACTS.open() as f:
        for line in f:
            act = json.loads(line)
            titles[act["celex"]] = act["title"] or ""

    jobs = [(doc_id, titles.get(doc_id, "")) for doc_id in pdf_chunks]
    chunks = []
    from_html = 0
    with ProcessPoolExecutor(max_workers=6) as pool:
        for job, result in tqdm(zip(jobs, pool.map(chunk_html_one, jobs, chunksize=4)), total=len(jobs), desc="html chunks"):
            if result is None:
                chunks += pdf_chunks[job[0]]
            else:
                chunks += result
                from_html += 1
    with gzip.open(OUT / "html_chunks.jsonl.gz", "wt") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk) + "\n")
    print(f"html: {len(chunks):,} chunks ({from_html:,} acts from HTML, {len(jobs) - from_html:,} from PDF)")


# --- embed (Kaggle) -------------------------------------------------------------


def embed(folder: Path, name: str) -> None:
    """Embed one chunk set ("new" or "html") with bge-base. Needs only
    sentence-transformers, so it runs on a Kaggle GPU with the
    <name>_chunks.jsonl.gz file uploaded."""
    from sentence_transformers import SentenceTransformer

    texts = [chunk["text"] for chunk in read_chunks(folder, name)]
    model = SentenceTransformer(MODEL)
    model.max_seq_length = 512
    if model.device.type == "cuda":
        model = model.half()  # ~2x faster; vectors are stored in half precision anyway
    started = time.perf_counter()
    vectors = model.encode(texts, batch_size=128, normalize_embeddings=True, show_progress_bar=True)
    np.save(Path("/kaggle/working" if Path("/kaggle").exists() else folder) / f"{name}_vectors.npy",
            vectors.astype(np.float16))
    print(f"{len(texts)} chunks in {time.perf_counter() - started:.0f} s")


# --- score ----------------------------------------------------------------------


def letters(text: str) -> str:
    """Lowercase letters and digits only, so spacing and punctuation differences
    between the two parses do not matter."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def gold_spans(texts: list[str]) -> set[str]:
    """Every GOLD_SPAN-long run of the gold text."""
    spans = set()
    for text in texts:
        t = letters(text)
        for i in range(len(t) - GOLD_SPAN + 1):
            spans.add(t[i : i + GOLD_SPAN])
    return spans


def is_correct(chunk: dict, gold_docs: list[str], spans: set[str]) -> bool:
    """From a gold act and sharing a GOLD_SPAN-long run with the gold text."""
    if chunk["doc_id"] not in gold_docs:
        return False
    t = letters(chunk["text"])
    for i in range(len(t) - GOLD_SPAN + 1):
        if t[i : i + GOLD_SPAN] in spans:
            return True
    return False


def search_and_score(name: str, chunks: list[dict], vectors: np.ndarray, gold: list[dict], questions) -> None:
    """Exact search for every question, then Hit@k and MRR@6 by the text rule.
    Headers are left out of the match, so they cannot fake a hit."""
    # Similarity of every chunk to every question, 50,000 chunks at a time:
    # converting all vectors to float32 at once would take over 1 GB.
    scores = np.empty((len(vectors), len(questions)), dtype=np.float32)
    for start in range(0, len(vectors), 50_000):
        block = vectors[start : start + 50_000].astype(np.float32)
        scores[start : start + 50_000] = block @ questions.T

    first_hits = []
    top_chars = 0
    for column, q in enumerate(gold):
        top = np.argsort(-scores[:, column])[:50]
        spans = gold_spans(q["texts"])
        first = None
        for position, index in enumerate(top, start=1):
            chunk = chunks[index]
            body = chunk["text"].split("\n", 1)[-1] if name != "old" else chunk["text"]
            if is_correct({"doc_id": chunk["doc_id"], "text": body}, q["doc_ids"], spans):
                first = position
                break
        first_hits.append(first)
        top_chars += sum(len(chunks[i]["text"]) for i in top[:K])
    n = len(gold)
    hit = "  ".join(f"Hit@{k}: {sum(1 for r in first_hits if r and r <= k) / n:.2f}" for k in (6, 10, 20, 50))
    mrr = sum(1 / r for r in first_hits if r and r <= K) / n
    print(f"{name:5} {len(chunks):8,} chunks   {hit}   MRR@{K}: {mrr:.2f}   (top {K} = {top_chars / n:,.0f} chars)")


def score() -> None:
    """Compare old and new chunking on the same acts with the same model."""
    from sentence_transformers import SentenceTransformer

    gold = json.loads((OUT / "gold.json").read_text())
    model = SentenceTransformer(MODEL)
    questions = model.encode(
        [QUERY_PREFIX + q["question"] for q in gold], normalize_embeddings=True
    )

    for name in ("old", "new", "html"):
        if not (OUT / f"{name}_vectors.npy").exists():
            continue
        chunks = read_chunks(OUT, name)
        vectors = np.load(OUT / f"{name}_vectors.npy")
        search_and_score(name, chunks, vectors, gold, questions)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("step", choices=["prepare", "prepare-html", "embed", "score"])
    parser.add_argument("--dir", type=Path, default=OUT, help="embed: folder with the chunks file")
    parser.add_argument("--name", default="new", help='embed: which chunk set, "new" or "html"')
    args = parser.parse_args()
    if args.step == "prepare":
        prepare()
    elif args.step == "prepare-html":
        prepare_html()
    elif args.step == "embed":
        embed(args.dir, args.name)
    else:
        score()


if __name__ == "__main__":
    main()
