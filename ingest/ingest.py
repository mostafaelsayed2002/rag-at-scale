"""Ingest the EU acts in force: PDF -> clean text -> chunks -> vectors -> Postgres.

    uv run --package rag-ingest python ingest/ingest.py chunk --count-only   # count, write nothing
    uv run --package rag-ingest python ingest/ingest.py chunk                # PDFs -> chunk shards
    uv run --package rag-ingest python ingest/ingest.py embed                # shards -> vectors (GPU)
    uv run --package rag-ingest python ingest/ingest.py load                 # -> Postgres
    uv run --package rag-ingest python ingest/ingest.py all                  # the three in a row
    uv run --package rag-ingest python ingest/ingest.py status               # where each stage is

Three stages with files in between (data/eurlex/work/), so each can be
stopped and rerun, and the slow one, embedding, can run elsewhere: the same
embed.py runs on a free Kaggle or Colab GPU. Every stage resumes where it
stopped; Ctrl+C is always safe.
"""

import argparse
import hashlib
import json
import os
import statistics
import sys
import time
from chunk import chunk_pages, tokenizer_file, use_tokenizer_file
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import psycopg
import work
from config import settings
from models import DocumentInfo
from parse import quality, read_pages
from rich.console import Console
from rich.panel import Panel
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
from rich.table import Table

# The Hub warns on every anonymous download; public models need no token.
os.environ.setdefault("HF_HUB_VERBOSITY", "error")

console = Console()
ROOT = Path(__file__).resolve().parent.parent


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)


def header(stage: str, lines: list[str]) -> None:
    console.print(Panel.fit(f"[bold]{stage}[/]\n" + "\n".join(lines), border_style="blue"))


def progress_bar(label: str, *fields: str) -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn(f"[bold blue]{label}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        *(TextColumn(f) for f in fields),
        TimeElapsedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        console=console,
    )


# --- Stage 1: chunk ------------------------------------------------------------


def file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def process(act: dict) -> tuple[DocumentInfo, list]:
    """One PDF -> its document record and chunks. Runs in a worker process."""
    path = str(settings.pdf_dir / f"{act['celex']}.pdf")
    doc = DocumentInfo(
        doc_id=act["celex"],
        path=path,
        title=act.get("title"),
        act_type=act.get("type"),
        date=act.get("date"),
        topics=act.get("topics", []),
        sha256=file_sha256(path),
    )
    try:
        pages, doc.page_count = read_pages(path)
    except RuntimeError:  # a corrupt PDF (pymupdf's errors derive from it): skipped, never fatal
        doc.status = "unreadable"
        return doc, []
    doc.status = quality(pages, doc.page_count)
    if doc.status != "ok":
        return doc, []
    chunks = chunk_pages(doc.doc_id, pages)
    doc.chunk_count = len(chunks)
    return doc, chunks


def select_acts(args) -> list[dict]:
    """Acts from the download list whose PDF is on disk, after any filters."""
    if not settings.acts_file.exists():
        sys.exit(f"No {rel(settings.acts_file)}: run ingest/download.py first.")
    acts = [json.loads(line) for line in settings.acts_file.read_text().splitlines()]
    on_disk = {p.stem for p in settings.pdf_dir.glob("*.pdf")}
    acts = [a for a in acts if a["celex"] in on_disk]
    if args.only:
        acts = [a for a in acts if args.only.lower() in a["celex"].lower()]
    if args.topic:
        acts = [a for a in acts if any(args.topic.lower() in t.lower() for t in a.get("topics", []))]
    if args.limit:
        acts = acts[: args.limit]
    return acts


def cmd_chunk(args) -> None:
    count_only = args.count_only
    acts = select_acts(args)
    done = set() if count_only else work.done_doc_ids()
    todo = [a for a in acts if a["celex"] not in done]
    workers = args.workers or max(1, (os.cpu_count() or 2) - 2)

    header(
        "Stage 1 · chunk" + (" · count only (nothing is written)" if count_only else ""),
        [
            (
                f"[dim]PDFs on disk:[/] {len(acts):,}   [dim]already chunked:[/] {len(acts) - len(todo):,}"
                f"   [dim]to do:[/] {len(todo):,}"
            ),
            (
                f"[dim]Chunks:[/] {settings.chunk_chars} chars, {settings.overlap_chars} overlap, "
                f"≤ {settings.max_tokens} tokens ({settings.embedding_model})"
            ),
            f"[dim]Workers:[/] {workers}"
            + ("" if count_only else f"   [dim]Output:[/] {rel(work.CHUNKS_DIR)}/"),
        ],
    )
    if not todo:
        console.print("[green]✓[/] Nothing to do.")
        return

    shard = max(work.shards(), default=0) + 1
    pending_docs: list[DocumentInfo] = []
    pending_chunks: list = []
    stats = {"docs": 0, "chunks": 0, "pages": 0, "skipped": {}, "tokens": [], "shards": 0}

    def flush() -> None:
        nonlocal shard
        if count_only or not pending_docs:
            return
        work.write_shard(shard, pending_docs, pending_chunks)
        stats["shards"] += 1
        shard += 1
        pending_docs.clear()
        pending_chunks.clear()

    progress = progress_bar(
        "Chunking",
        "· [green]{task.fields[chunks]:,} chunks[/]",
        "· [yellow]{task.fields[skipped]} skipped[/]",
        "· {task.fields[rate]}",
    )
    started = time.perf_counter()
    try:
        # Workers load the tokenizer from this local file instead of the network.
        pool = ProcessPoolExecutor(
            max_workers=workers, initializer=use_tokenizer_file, initargs=(tokenizer_file(),)
        )
        with progress, pool:
            task = progress.add_task("chunk", total=len(todo), chunks=0, skipped=0, rate="")
            for doc, chunks in pool.map(process, todo, chunksize=8):
                stats["docs"] += 1
                stats["pages"] += doc.page_count
                if doc.status != "ok":
                    stats["skipped"][doc.status] = stats["skipped"].get(doc.status, 0) + 1
                stats["chunks"] += len(chunks)
                stats["tokens"].extend(c.tokens for c in chunks)
                pending_docs.append(doc)
                pending_chunks.extend(chunks)
                if len(pending_docs) >= settings.shard_docs:
                    flush()
                progress.update(
                    task,
                    advance=1,
                    chunks=stats["chunks"],
                    skipped=sum(stats["skipped"].values()),
                    rate=f"{stats['docs'] / (time.perf_counter() - started):.0f} docs/s",
                )
            flush()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/] Finished shards are kept; rerun the same command to continue.")
        return

    seconds = time.perf_counter() - started
    show_chunk_summary(stats, seconds, count_only)
    if not count_only:
        save_stats("chunk", stats, seconds)


def show_chunk_summary(stats: dict, seconds: float, count_only: bool) -> None:
    tokens = sorted(stats["tokens"])
    table = Table(title="Chunking summary", title_style="bold", show_header=False)
    table.add_row("Documents", f"{stats['docs']:,}")
    table.add_row("Pages", f"{stats['pages']:,}")
    for reason, count in sorted(stats["skipped"].items()):
        table.add_row(f"  skipped: {reason}", f"[yellow]{count:,}")
    table.add_row("Chunks", f"[bold green]{stats['chunks']:,}")
    usable = stats["docs"] - sum(stats["skipped"].values())
    if usable:
        table.add_row("Chunks per document", f"{stats['chunks'] / usable:.1f}")
    if tokens:
        p95 = tokens[int(len(tokens) * 0.95) - 1]
        table.add_row(
            "Tokens per chunk",
            f"median {statistics.median(tokens):.0f} · p95 {p95} · max {tokens[-1]}",
        )
        over = sum(1 for t in tokens if t > settings.max_tokens)
        table.add_row(f"Over {settings.max_tokens} tokens", f"{over:,}" + (" [red](truncated when embedded)" if over else ""))
    table.add_row("Time", f"{seconds:,.0f} s ({stats['docs'] / max(seconds, 1e-9):.0f} docs/s)")
    if not count_only:
        table.add_row("Shards written", f"{stats['shards']:,}")
    console.print(table)
    if count_only:
        console.print("[dim]Count only: nothing was written. Drop --count-only to create the shards.[/]")


def save_stats(stage: str, stats: dict, seconds: float) -> None:
    """Measured numbers for docs/findings.md, one file per stage run."""
    out = {k: v for k, v in stats.items() if k != "tokens"}
    if stats.get("tokens"):
        t = sorted(stats["tokens"])
        out["tokens"] = {"median": statistics.median(t), "p95": t[int(len(t) * 0.95) - 1], "max": t[-1]}
    out["seconds"] = round(seconds, 1)
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    (settings.work_dir / f"stats-{stage}.json").write_text(json.dumps(out, indent=2))


# --- Stage 2: embed ------------------------------------------------------------


def cmd_embed(args) -> None:
    import embed

    shards = work.shards()
    missing = [s for s in shards if not work.vectors_path(s).exists()]
    header(
        "Stage 2 · embed",
        [
            (
                f"[dim]Shards:[/] {len(shards):,}   [dim]embedded:[/] {len(shards) - len(missing):,}"
                f"   [dim]to do:[/] {len(missing):,}"
            ),
            f"[dim]Model:[/] {settings.embedding_model}   [dim]Batch:[/] {args.batch_size}",
            "[dim]Tip:[/] this is the slow stage; embed.py also runs on a free Kaggle GPU.",
        ],
    )
    if not missing:
        console.print("[green]✓[/] Nothing to do." if shards else "[yellow]No chunk shards yet: run `chunk` first.")
        return
    stats = embed.run(settings.work_dir, settings.embedding_model, args.batch_size, args.device, args.limit)
    if stats["embedded"]:
        rate = stats["chunks"] / stats["seconds"]
        console.print(
            f"[green]✓[/] Embedded {stats['chunks']:,} chunks in {stats['embedded']} shards "
            f"on {stats['device']} · {rate:.0f} chunks/s · {stats['seconds'] / 60:.1f} min"
        )
        save_stats("embed", stats, stats["seconds"])


# --- Stage 3: load -------------------------------------------------------------


def cmd_load(args) -> None:
    import store

    ready = [s for s in work.shards() if work.vectors_path(s).exists()]
    header(
        "Stage 3 · load",
        [f"[dim]Embedded shards ready:[/] {len(ready):,}", "[dim]Target:[/] Postgres (halfvec)"],
    )
    if not ready:
        console.print("[yellow]No embedded shards yet: run `chunk` and `embed` first.")
        return

    try:
        conn = store.connect()
        store.check_schema(conn)
    except (store.SchemaError, psycopg.Error) as exc:  # no database, wrong schema, bad login
        console.print(f"[bold red]Cannot load:[/] {exc}")
        return

    with conn:
        stored = store.stored_hashes(conn)
        started = time.perf_counter()
        stats = {"docs": 0, "chunks": 0, "unchanged": 0, "shards": 0}
        progress = progress_bar(
            "Loading", "· [green]{task.fields[chunks]:,} chunks[/]", "· {task.fields[unchanged]} unchanged"
        )
        try:
            with progress:
                task = progress.add_task("load", total=len(ready), chunks=0, unchanged=0)
                for shard in ready:
                    docs = [d for d in work.read_docs(shard) if d.status == "ok"]
                    fresh = [d for d in docs if args.force or stored.get(d.doc_id) != d.sha256]
                    stats["unchanged"] += len(docs) - len(fresh)
                    if fresh:
                        chunks = work.read_chunks(shard)
                        vectors = np.load(work.vectors_path(shard))
                        if len(vectors) != len(chunks):
                            raise RuntimeError(
                                f"shard {shard}: {len(chunks)} chunks but {len(vectors)} vectors; "
                                f"delete {rel(work.vectors_path(shard))} and embed again"
                            )
                        stats["chunks"] += store.store_shard(conn, fresh, chunks, vectors)
                        stats["docs"] += len(fresh)
                    stats["shards"] += 1
                    progress.update(task, advance=1, chunks=stats["chunks"], unchanged=stats["unchanged"])
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped.[/] Loaded shards are committed; rerun to continue.")
            return
        seconds = time.perf_counter() - started
        totals = store.corpus_stats(conn)

    table = Table(title="Load summary", title_style="bold", show_header=False)
    table.add_row("Documents loaded", f"[green]{stats['docs']:,}")
    table.add_row("Chunks loaded", f"[green]{stats['chunks']:,}")
    table.add_row("Unchanged (skipped)", f"{stats['unchanged']:,}")
    table.add_row("Time", f"{seconds:,.0f} s")
    table.add_row("Database now holds", f"{totals['documents']:,} documents · {totals['chunks']:,} chunks")
    console.print(table)
    save_stats("load", stats, seconds)


# --- status ------------------------------------------------------------------


def cmd_status(args) -> None:
    acts = sum(1 for _ in settings.acts_file.open()) if settings.acts_file.exists() else 0
    pdfs = len(list(settings.pdf_dir.glob("*.pdf"))) if settings.pdf_dir.exists() else 0
    shards = work.shards()
    docs = [d for s in shards for d in work.read_docs(s)]
    chunks = sum(d.chunk_count for d in docs)
    embedded = [s for s in shards if work.vectors_path(s).exists()]
    embedded_chunks = sum(d.chunk_count for s in embedded for d in work.read_docs(s))

    table = Table(title="Ingestion status", title_style="bold")
    table.add_column("Stage")
    table.add_column("Progress", justify="right")
    table.add_row("Acts listed", f"{acts:,}")
    table.add_row("PDFs downloaded", f"{pdfs:,}" + (f" / {acts:,}" if acts else ""))
    table.add_row("Documents chunked", f"{len(docs):,} / {pdfs:,}")
    table.add_row("Chunks", f"{chunks:,}")
    table.add_row("Chunks embedded", f"{embedded_chunks:,} / {chunks:,}")
    try:
        import store

        with store.connect() as conn:
            totals = store.corpus_stats(conn)
        table.add_row("In Postgres", f"{totals['chunks']:,} chunks · {totals['documents']:,} documents")
    except (store.SchemaError, psycopg.Error) as exc:
        table.add_row("In Postgres", f"[dim]unavailable ({type(exc).__name__})")
    console.print(table)


def cmd_all(args) -> None:
    args.count_only = False
    cmd_chunk(args)
    args.limit = None  # a document limit for chunking, not a shard limit for embedding
    cmd_embed(args)
    cmd_load(args)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def selection(p):
        p.add_argument("--limit", type=int, help="only the first N documents")
        p.add_argument("--only", help="only CELEX ids containing this text, e.g. 32016R")
        p.add_argument("--topic", help='only acts with a matching topic, e.g. "data protection"')
        p.add_argument("--workers", type=int, help="parallel processes (default: cores - 2)")

    def embedding(p):
        p.add_argument("--batch-size", type=int, default=settings.embed_batch)
        p.add_argument("--device", help="cuda, mps or cpu (default: the fastest available)")

    p = sub.add_parser("chunk", help="PDFs -> chunk shards")
    selection(p)
    p.add_argument("--count-only", action="store_true", help="count chunks and tokens, write nothing")
    p.set_defaults(func=cmd_chunk)

    p = sub.add_parser("embed", help="chunk shards -> vectors")
    embedding(p)
    p.add_argument("--limit", type=int, help="only the first N shards")
    p.set_defaults(func=cmd_embed)

    p = sub.add_parser("load", help="chunks + vectors -> Postgres")
    p.add_argument("--force", action="store_true", help="reload documents even if unchanged")
    p.set_defaults(func=cmd_load)

    p = sub.add_parser("all", help="chunk, embed and load in a row")
    selection(p)
    embedding(p)
    p.add_argument("--force", action="store_true", help="reload documents even if unchanged")
    p.set_defaults(func=cmd_all)

    sub.add_parser("status", help="how far each stage has got").set_defaults(func=cmd_status)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
