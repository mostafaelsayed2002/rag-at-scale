"""Embed the chunk shards into vector shards, on whatever GPU is available.

    python embed.py --work data/eurlex/work            # on the Mac (M1 GPU)
    python embed.py --work /kaggle/working/work        # on a Kaggle / Colab GPU

Self-contained on purpose: it imports nothing from this project, so the same
file runs in a notebook after uploading work/chunks/. Resumes shard by shard:
a shard whose vectors already exist is skipped.

Vectors are L2-normalised and stored as float16, the precision pgvector's
halfvec keeps anyway, which halves the files to copy back.
"""

import argparse
import gzip
import json
import os
import re
import time
from pathlib import Path

import numpy as np

# Quiet the Hub: public models need no token, and its bars clash with ours.
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

DEFAULT_MODEL = "BAAI/bge-base-en-v1.5"
SHARD = re.compile(r"shard-(\d+)\.docs\.jsonl$")


def pick_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def load_model(name: str, device: str):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(name, device=device)
    # Half precision on a GPU: ~1.5-2x faster, and the vectors end up in
    # half precision in the database anyway.
    return model.half() if device in ("cuda", "mps") else model


def finished_shards(chunks_dir: Path) -> list[int]:
    return sorted(int(m.group(1)) for p in chunks_dir.iterdir() if (m := SHARD.search(p.name)))


def chunk_count(chunks_dir: Path, shard: int) -> int:
    """From the small docs file, so the total is known without reading every chunk."""
    lines = (chunks_dir / f"shard-{shard:05d}.docs.jsonl").read_text().splitlines()
    return sum(json.loads(line)["chunk_count"] for line in lines)


def read_texts(chunks_dir: Path, shard: int) -> list[str]:
    with gzip.open(chunks_dir / f"shard-{shard:05d}.chunks.jsonl.gz", "rt", encoding="utf-8") as fh:
        return [json.loads(line)["text"] for line in fh]


def encode(model, texts: list[str], batch_size: int, on_batch=None) -> np.ndarray:
    """Embed texts, longest first: similar lengths share a batch, so little
    compute is spent on padding. The original order is restored at the end."""
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]), reverse=True)
    # Renamed in sentence-transformers 6; the old name still works on older installs.
    dim = getattr(model, "get_embedding_dimension", None) or model.get_sentence_embedding_dimension
    out = np.empty((len(texts), dim()), dtype=np.float16)
    for start in range(0, len(order), batch_size):
        idx = order[start : start + batch_size]
        vectors = model.encode(
            [texts[i] for i in idx],
            batch_size=batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        out[idx] = vectors.astype(np.float16)
        if on_batch:
            on_batch(len(idx))
    return out


def run(work: Path, model_name: str, batch_size: int, device: str | None, limit: int | None) -> dict:
    chunks_dir, vectors_dir = work / "chunks", work / "vectors"
    vectors_dir.mkdir(parents=True, exist_ok=True)

    shards = finished_shards(chunks_dir)
    todo = [s for s in shards if not (vectors_dir / f"shard-{s:05d}.npy").exists()]
    if limit:
        todo = todo[:limit]
    stats = {"shards": len(shards), "skipped": len(shards) - len(todo), "embedded": 0, "chunks": 0}
    if not todo:
        return stats

    device = device or pick_device()
    # Texts are read one shard at a time: all of them at once would be ~1.6 GB.
    total = sum(chunk_count(chunks_dir, s) for s in todo)
    started = time.perf_counter()

    try:
        from rich.console import Console
        from rich.progress import (
            BarColumn,
            MofNCompleteColumn,
            Progress,
            SpinnerColumn,
            TaskProgressColumn,
            TextColumn,
            TimeElapsedColumn,
            TimeRemainingColumn,
        )

        console = Console()
        console.print(f"[bold]Embedding[/] {total:,} chunks in {len(todo)} shards "
                      f"· model [cyan]{model_name}[/] · device [cyan]{device}[/]")
        progress = Progress(
            SpinnerColumn(), TextColumn("[bold blue]Embedding"), BarColumn(),
            MofNCompleteColumn(), TaskProgressColumn(),
            TextColumn("· shard {task.fields[shard]}"), TextColumn("· {task.fields[rate]}"),
            TimeElapsedColumn(), TextColumn("ETA"), TimeRemainingColumn(), console=console,
        )
    except ImportError:  # a bare notebook without rich: plain prints instead
        progress = None
        print(f"Embedding {total:,} chunks in {len(todo)} shards on {device}")

    model = load_model(model_name, device)
    task = progress.add_task("embed", total=total, shard="", rate="") if progress else None

    def advance(n: int) -> None:
        stats["chunks"] += n
        rate = f"{stats['chunks'] / (time.perf_counter() - started):.0f} chunks/s"
        if progress:
            progress.update(task, advance=n, rate=rate)

    def work_through() -> None:
        for shard in todo:
            if progress:
                progress.update(task, shard=f"{shard:05d}")
            vectors = encode(model, read_texts(chunks_dir, shard), batch_size, advance)
            target = vectors_dir / f"shard-{shard:05d}.npy"
            tmp = target.with_suffix(".tmp.npy")
            np.save(tmp, vectors)
            tmp.rename(target)  # only a complete file gets the final name
            stats["embedded"] += 1
            if not progress:
                print(f"shard {shard:05d}: {len(vectors):,} chunks, {stats['chunks']:,}/{total:,}")

    if progress:
        with progress:
            work_through()
    else:
        work_through()
    stats["seconds"] = time.perf_counter() - started
    stats["device"] = device
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--work", type=Path, required=True, help="folder with chunks/ (vectors/ is created)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--device", help="cuda, mps or cpu (default: the fastest available)")
    parser.add_argument("--limit", type=int, help="only the first N shards, for testing")
    args = parser.parse_args()
    try:
        stats = run(args.work, args.model, args.batch_size, args.device, args.limit)
    except KeyboardInterrupt:
        print("\nStopped. Finished shards are kept; rerun to continue.")
        return
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
