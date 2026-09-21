"""Ingest the corpus: PDF -> chunks -> embeddings -> Postgres.

    uv run python ingest/ingest.py              # everything not already stored
    uv run python ingest/ingest.py --force      # re-ingest even if unchanged
    uv run python ingest/ingest.py --only gdpr  # one document, by name

A document is skipped when its content hash matches the stored one, so runs
are cheap to repeat and safe to interrupt: whatever finished stays finished.
"""

import argparse
import hashlib
import json
import logging
import sys
import time
from chunk import chunking
from pathlib import Path

import pymupdf
from embed import embed_chunks
from load import load_pdfs
from models import DocumentInfo
from store import connect, corpus_stats, is_unchanged, store_document

logger = logging.getLogger("ingest")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
METADATA = DATA_DIR / "metadata" / "documents.jsonl"

# $0.20 per million tokens, and a token is roughly four characters of English.
USD_PER_MILLION_TOKENS = 0.20
CHARS_PER_TOKEN = 4


def file_sha256(path: Path) -> str:
    """Content hash, read in 1 MB blocks so large files don't fill memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_metadata() -> dict[str, dict]:
    """Corpus metadata keyed by document id, for titles and source URLs.

    Missing metadata is not fatal: the document is still ingested, just
    without a title, so a newly added PDF works before the metadata catches up.
    """
    if not METADATA.exists():
        logger.warning("no metadata file at %s; titles will be empty", METADATA)
        return {}
    rows = (json.loads(line) for line in METADATA.read_text().splitlines() if line.strip())
    return {Path(row["local_path"]).stem: row for row in rows}


def describe(document: pymupdf.Document, metadata: dict[str, dict]) -> DocumentInfo:
    """Everything the database needs about a document, besides its chunks."""
    path = Path(document.name)
    doc_id = path.stem
    row = metadata.get(doc_id, {})
    return DocumentInfo(
        doc_id=doc_id,
        path=str(path),
        sha256=file_sha256(path),
        page_count=document.page_count,
        title=row.get("title"),
        source_url=row.get("source_url"),
        extra={
            "source_organization": row.get("source_organization"),
            "document_type": row.get("document_type"),
            "celex_number": row.get("celex_number"),
            "publication_date": row.get("publication_date"),
            # Top folder under data/: legislation, edpb, curia, and so on.
            "collection": path.resolve().relative_to(DATA_DIR).parts[0],
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-ingest unchanged documents")
    parser.add_argument("--limit", type=int, help="stop after this many documents")
    parser.add_argument("--only", help="only documents whose id contains this text")
    parser.add_argument("--dry-run", action="store_true", help="chunk but do not embed or store")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-7s %(message)s")
    # One line per HTTP call to Google buries the progress messages.
    for noisy in ("httpx", "google_genai", "google.genai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    metadata = load_metadata()
    started = time.perf_counter()
    documents = skipped = failed = chunks_total = chars_total = 0

    with connect() as conn:
        for document in load_pdfs(str(DATA_DIR)):
            try:
                doc = describe(document, metadata)

                if args.only and args.only not in doc.doc_id:
                    continue
                if args.limit is not None and documents >= args.limit:
                    break
                if not args.force and not args.dry_run and is_unchanged(conn, doc):
                    logger.info("skipping %s (unchanged)", doc.doc_id)
                    skipped += 1
                    continue

                chunks = chunking(document)
                chars = sum(len(c.text) for c in chunks)

                if args.dry_run:
                    logger.info("%s: %d chunks, %d chars (dry run)", doc.doc_id, len(chunks), chars)
                else:
                    store_document(conn, doc, embed_chunks(chunks))

                documents += 1
                chunks_total += len(chunks)
                chars_total += chars
            except Exception:
                # One unreadable PDF or one failed API call should not end the
                # run: its transaction is rolled back and the rest continue.
                logger.exception("failed on %s", document.name)
                failed += 1
            finally:
                document.close()

        elapsed = time.perf_counter() - started
        cost = chars_total / CHARS_PER_TOKEN / 1_000_000 * USD_PER_MILLION_TOKENS
        logger.info(
            "%d documents, %d chunks in %.1fs (%d skipped, %d failed), about $%.2f of embedding",
            documents,
            chunks_total,
            elapsed,
            skipped,
            failed,
            cost,
        )
        if not args.dry_run:
            logger.info("database now holds %s", corpus_stats(conn))

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
