"""Chunk every act by its legal structure, into a second work folder.

    WORK_NAME=work_v2 uv run --package rag-ingest python ingest/rechunk.py
    WORK_NAME=work_v2 uv run --package rag-ingest python ingest/rechunk.py --limit 50   # a test

Each act is read from its EUR-Lex HTML (data/eurlex/html, see
download_html.py) and chunked by html_chunk.py: from the tags, or, for old
plain pages, from the text. The ~7% of acts that exist only as PDF are left
out (status "no_html").

The chunks go into the same shard files as ingest.py's chunk stage, so its
embed and load stages work on them unchanged:

    WORK_NAME=work_v2 uv run --package rag-ingest python ingest/ingest.py embed

Safe to stop and rerun: finished shards are kept and their acts skipped.
"""

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor

from chunk import count_tokens, tokenizer_file, use_tokenizer_file
from config import settings
from models import Chunk, DocumentInfo
from tqdm import tqdm

import work

HTML_DIR = settings.corpus_dir / "html"
MAX_TOKENS = 480  # header included; the model reads at most 512


def tokens(text: str) -> int:
    return count_tokens([text])[0]


def file_sha256(path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def process(act: dict) -> tuple[DocumentInfo, list[Chunk]]:
    """One act -> its document record and chunks. Runs in a worker process."""
    from html_chunk import html_chunks

    celex = act["celex"]
    title = act.get("title") or ""
    doc = DocumentInfo(
        doc_id=celex,
        path="",
        title=act.get("title"),
        act_type=act.get("type"),
        date=act.get("date"),
        topics=act.get("topics", []),
    )

    html = None
    for suffix in ("xhtml", "html"):
        if (HTML_DIR / f"{celex}.{suffix}").exists():
            html = HTML_DIR / f"{celex}.{suffix}"
            break
    if html is None:
        # HTML only: the ~7% of acts that exist only as PDF are left out.
        doc.status = "no_html"
        return doc, []

    try:
        doc.path = str(html)
        pieces = html_chunks(html.read_bytes(), title, tokens, MAX_TOKENS)
    except Exception as error:  # one broken file must not stop 43,000
        doc.status = f"error: {type(error).__name__}"
        return doc, []

    doc.sha256 = file_sha256(html)
    if not pieces:
        doc.status = "no_text"
        return doc, []

    texts = [piece["text"] for piece in pieces]
    counts = count_tokens(texts)
    chunks = []
    for index, (piece, n) in enumerate(zip(pieces, counts)):
        chunks.append(
            Chunk(
                doc_id=celex,
                index=index,
                text=piece["text"],
                page_start=piece["page_start"],
                page_end=piece["page_end"],
                tokens=n,
            )
        )
    doc.chunk_count = len(chunks)
    return doc, chunks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="only the first N acts, for testing")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if settings.work_name == "work":
        raise SystemExit("Set WORK_NAME (e.g. work_v2): this would mix with the current chunks.")

    acts = [json.loads(line) for line in settings.acts_file.read_text().splitlines()]
    done = work.done_doc_ids()
    todo = [a for a in acts if a["celex"] not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(acts):,} acts, {len(done):,} already chunked, {len(todo):,} to do -> {work.CHUNKS_DIR}")

    shard = max(work.shards(), default=0) + 1
    docs: list[DocumentInfo] = []
    chunks: list[Chunk] = []
    statuses: dict[str, int] = {}
    total_chunks = 0
    pool = ProcessPoolExecutor(
        max_workers=args.workers, initializer=use_tokenizer_file, initargs=(tokenizer_file(),)
    )
    with pool:
        for doc, doc_chunks in tqdm(pool.map(process, todo, chunksize=8), total=len(todo), desc="acts"):
            docs.append(doc)
            chunks += doc_chunks
            total_chunks += len(doc_chunks)
            statuses[doc.status] = statuses.get(doc.status, 0) + 1
            if len(docs) >= settings.shard_docs:
                work.write_shard(shard, docs, chunks)
                shard += 1
                docs, chunks = [], []
    if docs:
        work.write_shard(shard, docs, chunks)
    print(f"done: {total_chunks:,} chunks; acts by status: {statuses}")


if __name__ == "__main__":
    main()
