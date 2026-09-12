"""Download arXiv abstracts, embed them, and insert them into pgvector.

    uv run python ingest/ingest.py --limit 10000

Kaggle credentials are required: either ~/.kaggle/kaggle.json or the
KAGGLE_USERNAME and KAGGLE_KEY environment variables.
"""

import argparse
import csv
import os
import sys
import time
from itertools import islice

import kagglehub
import psycopg
from fastembed import TextEmbedding

DATASET = "spsayakpaul/arxiv-paper-abstracts"
CSV_NAME = "arxiv_data.csv"
# 384 dimensions, matching the embedding column in 001_init.sql.
MODEL = "BAAI/bge-small-en-v1.5"

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://rag:rag@localhost:5432/rag")


def read_rows(path: str, limit: int):
    """Yield (text, source) pairs from the CSV, newest-first order not required."""
    with open(path, newline="", encoding="utf-8") as handle:
        for row in islice(csv.DictReader(handle), limit):
            title = (row.get("titles") or "").strip()
            summary = (row.get("summaries") or "").strip()
            if not summary:
                continue
            # Title and abstract are embedded together: the title carries terms
            # the abstract often omits, and both are what a searcher means.
            yield f"{title}\n\n{summary}", title


def batched(iterable, size: int):
    iterator = iter(iterable)
    while batch := list(islice(iterator, size)):
        yield batch


def main() -> None:
    # Line buffering, so progress appears immediately even when the output is
    # piped or redirected rather than going to a terminal.
    sys.stdout.reconfigure(line_buffering=True)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10_000, help="rows to ingest")
    parser.add_argument("--batch-size", type=int, default=256, help="rows per embed/insert")
    args = parser.parse_args()

    # Cached after the first run, so reruns do not re-download.
    csv_path = os.path.join(kagglehub.dataset_download(DATASET), CSV_NAME)
    print(f"corpus: {csv_path}")

    # Downloads ~130MB of ONNX weights on first use, then caches them.
    model = TextEmbedding(MODEL)
    print(f"model:  {MODEL}")

    started = time.perf_counter()
    inserted = 0
    batches = 0

    with psycopg.connect(DATABASE_URL) as conn:
        for batch in batched(read_rows(csv_path, args.limit), args.batch_size):
            texts = [text for text, _ in batch]
            vectors = list(model.embed(texts))

            records = [
                (text, source, "[" + ",".join(f"{value:.6f}" for value in vector) + "]")
                for (text, source), vector in zip(batch, vectors)
            ]
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO chunks (text, source, embedding) VALUES (%s, %s, %s)",
                    records,
                )
            # Commit per batch: a crash then costs one batch, not the whole run.
            conn.commit()

            inserted += len(records)
            batches += 1
            elapsed = time.perf_counter() - started
            print(
                f"batch {batches:>3}  {inserted:>7} rows  "
                f"{inserted / elapsed:6.0f} rows/s  {elapsed:5.1f}s"
            )

    print(f"done: {inserted} rows in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
