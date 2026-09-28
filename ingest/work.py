"""The files the stages hand over to each other.

    work/chunks/shard-00001.chunks.jsonl.gz   the chunks of ~500 documents
    work/chunks/shard-00001.docs.jsonl        those documents (written last)
    work/vectors/shard-00001.npy              their embeddings, same order

A shard counts as done only once its docs file exists, and every file is
written under a temporary name and renamed when complete. So an interrupted
run never leaves a half shard that looks finished.
"""

import gzip
import json
import re
from pathlib import Path

from config import settings
from models import Chunk, DocumentInfo

CHUNKS_DIR = settings.work_dir / "chunks"
VECTORS_DIR = settings.work_dir / "vectors"
SHARD = re.compile(r"shard-(\d+)\.docs\.jsonl$")


def chunks_path(shard: int) -> Path:
    return CHUNKS_DIR / f"shard-{shard:05d}.chunks.jsonl.gz"


def docs_path(shard: int) -> Path:
    return CHUNKS_DIR / f"shard-{shard:05d}.docs.jsonl"


def vectors_path(shard: int) -> Path:
    return VECTORS_DIR / f"shard-{shard:05d}.npy"


def write_shard(shard: int, docs: list[DocumentInfo], chunks: list[Chunk]) -> None:
    CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = chunks_path(shard).with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.to_json(), ensure_ascii=False) + "\n")
    tmp.rename(chunks_path(shard))
    # The docs file last: its existence is what marks the shard as done.
    tmp = docs_path(shard).with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(d.to_json(), ensure_ascii=False) + "\n" for d in docs))
    tmp.rename(docs_path(shard))


def shards() -> list[int]:
    """Finished shards, in order. Leftovers of an interrupted write are removed."""
    if not CHUNKS_DIR.exists():
        return []
    done = sorted(int(m.group(1)) for p in CHUNKS_DIR.iterdir() if (m := SHARD.search(p.name)))
    for leftover in CHUNKS_DIR.glob("*.tmp"):
        leftover.unlink()
    for orphan in CHUNKS_DIR.glob("shard-*.chunks.jsonl.gz"):
        if int(orphan.name[6:11]) not in done:
            orphan.unlink()
    return done


def read_docs(shard: int) -> list[DocumentInfo]:
    return [DocumentInfo(**json.loads(line)) for line in docs_path(shard).read_text().splitlines()]


def read_chunks(shard: int) -> list[Chunk]:
    with gzip.open(chunks_path(shard), "rt", encoding="utf-8") as handle:
        return [Chunk(**json.loads(line)) for line in handle]


def done_doc_ids() -> set[str]:
    """Documents already chunked (or already judged unusable)."""
    return {d.doc_id for s in shards() for d in read_docs(s)}
