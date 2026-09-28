"""Download every EU act in force, as English PDFs, from the EU Publications Office.

    uv run --package rag-ingest python ingest/download.py               # everything
    uv run --package rag-ingest python ingest/download.py --limit 50    # a quick test
    uv run --package rag-ingest python ingest/download.py --list-only   # refresh the list

Two steps:
1. One SPARQL query per year lists the acts in force with their English PDF
   link (the endpoint refuses sorted pages past 10,000 rows, and no single
   year comes close). Saved to data/eurlex/acts.jsonl and reused next time.
2. The PDFs are fetched from CELLAR, the Publications Office's machine-access
   repository. The EUR-Lex website itself blocks automated downloads.

Safe to stop (Ctrl+C) and rerun: finished files are skipped, and a file only
gets its final name once it is complete, so a half-written download is never
mistaken for a finished one.
"""

import argparse
import asyncio
import collections
import json
import random
import shutil
import time
from pathlib import Path

import httpx
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

console = Console()

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "eurlex"
PDF_DIR = OUT / "pdf"
ACTS = OUT / "acts.jsonl"
FAILED = OUT / "failed.jsonl"

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
HEADERS = {"User-Agent": "rag-at-scale/0.1 (portfolio research project)"}
FIRST_YEAR = 1950

# Measured on a random sample of 120 acts: ~0.56 MB per PDF on average.
MB_PER_PDF = 0.56

# Acts in force only (repealed and expired acts are excluded), from CELEX
# sector 3 (legislation), that have an English PDF.
# The year is matched as a value, not with a string filter on the CELEX id:
# the server can look a value up directly but has to scan every act to apply
# a filter, which made each yearly query ~20x slower.
QUERY = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
SELECT ?celex ?type ?date ?title ?man WHERE {
  ?work cdm:resource_legal_year "%(year)s"^^<http://www.w3.org/2001/XMLSchema#gYear> ;
        cdm:resource_legal_in-force "true"^^<http://www.w3.org/2001/XMLSchema#boolean> ;
        cdm:resource_legal_id_celex ?celex .
  FILTER(STRSTARTS(STR(?celex), "3"))
  OPTIONAL { ?work cdm:work_has_resource-type ?type }
  OPTIONAL { ?work cdm:work_date_document ?date }
  ?expr cdm:expression_belongs_to_work ?work ;
        cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> .
  OPTIONAL { ?expr cdm:expression_title ?title }
  ?man cdm:manifestation_manifests_expression ?expr ;
       cdm:manifestation_type ?mtype .
  FILTER(STRSTARTS(STR(?mtype), "pdf"))
}
"""

# EUROVOC topics (the EU's subject thesaurus) for the same acts, in English.
# A separate query: joined into the one above, every topic would multiply the
# rows. An act usually has several topics, which is why they are stored as a
# list rather than as folders.
TOPICS_QUERY = """
PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
SELECT ?celex (GROUP_CONCAT(DISTINCT ?label; separator="|") AS ?topics) WHERE {
  ?work cdm:resource_legal_year "%(year)s"^^<http://www.w3.org/2001/XMLSchema#gYear> ;
        cdm:resource_legal_in-force "true"^^<http://www.w3.org/2001/XMLSchema#boolean> ;
        cdm:resource_legal_id_celex ?celex ;
        cdm:work_is_about_concept_eurovoc ?concept .
  FILTER(STRSTARTS(STR(?celex), "3"))
  ?concept skos:prefLabel ?label .
  FILTER(LANG(?label) = "en")
} GROUP BY ?celex
"""


# --- Step 1: the list of acts -------------------------------------------------


def sparql(client: httpx.Client, query: str) -> list[dict]:
    resp = client.post(
        SPARQL, data={"query": query}, headers={"Accept": "application/sparql-results+json"}
    )
    resp.raise_for_status()
    return resp.json()["results"]["bindings"]


def list_acts() -> list[dict]:
    """Every act in force with an English PDF and its topics, one row per act."""
    acts: dict[str, dict] = {}
    years = range(FIRST_YEAR, time.gmtime().tm_year + 1)

    with (
        Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Listing acts in force"),
            BarColumn(),
            TextColumn("{task.fields[year]}"),
            MofNCompleteColumn(),
            TextColumn("· [green]{task.fields[found]:,} acts"),
            TimeElapsedColumn(),
            console=console,
        ) as progress,
        httpx.Client(headers=HEADERS, timeout=300) as client,
    ):
        task = progress.add_task("list", total=len(years), year="", found=0)
        for year in years:
            progress.update(task, year=f"[dim]{year}")
            for row in sparql(client, QUERY % {"year": year}):
                # One act can come back several times (several types or
                # titles); the first row is enough.
                acts.setdefault(
                    row["celex"]["value"],
                    {
                        "celex": row["celex"]["value"],
                        "type": row.get("type", {}).get("value", "").rsplit("/", 1)[-1],
                        "date": row.get("date", {}).get("value"),
                        "title": row.get("title", {}).get("value"),
                        # Filled in from TOPICS_QUERY below; some acts have none.
                        "topics": [],
                        # DOC_1 is the act itself; annexes can follow as DOC_2...
                        "pdf_url": row["man"]["value"] + "/DOC_1",
                    },
                )
            for row in sparql(client, TOPICS_QUERY % {"year": year}):
                act = acts.get(row["celex"]["value"])
                if act is not None:
                    act["topics"] = sorted(row["topics"]["value"].split("|"))
            progress.update(task, advance=1, found=len(acts))

    return sorted(acts.values(), key=lambda a: a["celex"])


def show_list_summary(acts: list[dict]) -> None:
    years = sorted(a["date"][:4] for a in acts if a.get("date"))
    table = Table(title="Acts in force", title_style="bold", show_header=False, box=None)
    table.add_row("Total", f"[bold green]{len(acts):,}")
    if years:
        table.add_row("Adopted", f"{years[0]} – {years[-1]}")
    for kind, count in collections.Counter(a["type"] or "?" for a in acts).most_common(5):
        table.add_row(f"  {kind}", f"{count:,}")
    with_topics = sum(1 for a in acts if a.get("topics"))
    table.add_row("With topics", f"{with_topics:,} ({with_topics / max(len(acts), 1):.0%})")
    topics = collections.Counter(t for a in acts for t in a.get("topics", []))
    table.add_row("Distinct topics", f"{len(topics):,}")
    for topic, count in topics.most_common(5):
        table.add_row(f"  {topic}", f"{count:,}")
    table.add_row("Estimated size", f"~{len(acts) * MB_PER_PDF / 1024:.0f} GB")
    console.print(table)


# --- Step 2: the PDFs ---------------------------------------------------------


def pdf_path(celex: str) -> Path:
    return PDF_DIR / f"{celex}.pdf"


def candidate_urls(pdf_url: str) -> list[str]:
    """The act is usually DOC_1, but some older ones are stored as DOC_2 or later."""
    base = pdf_url.rsplit("/DOC_", 1)[0]
    return [f"{base}/DOC_{n}" for n in range(1, 5)]


async def fetch(client: httpx.AsyncClient, act: dict, retries: int = 4) -> tuple[int, str | None]:
    """Download one PDF. Returns (bytes written, error message or None)."""
    target = pdf_path(act["celex"])
    partial = target.with_suffix(".part")
    urls = candidate_urls(act["pdf_url"])
    for attempt in range(retries):
        try:
            for url in urls:
                resp = await client.get(url)
                if resp.status_code != 404:
                    break
            if resp.status_code in (429, 500, 502, 503, 504):
                raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
            if resp.status_code != 200:
                return 0, f"HTTP {resp.status_code}"
            if not resp.content.startswith(b"%PDF"):
                return 0, "not a PDF"
            partial.write_bytes(resp.content)
            partial.rename(target)
            return len(resp.content), None
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if attempt == retries - 1:
                return 0, f"{type(exc).__name__}: {exc}"
            # Back off, with jitter so the workers do not retry in lockstep.
            await asyncio.sleep(2**attempt * 2 + random.random())
    return 0, "gave up"


def check_disk(todo: int) -> bool:
    """Warn before starting a download the disk cannot hold."""
    need_gb = todo * MB_PER_PDF / 1024
    free_gb = shutil.disk_usage(OUT).free / 1024**3
    if free_gb < need_gb + 5:  # keep a few GB for the system
        console.print(
            f"[bold red]Not enough disk space:[/] ~{need_gb:.0f} GB needed, "
            f"{free_gb:.0f} GB free (keeping 5 GB spare)."
        )
        return False
    console.print(f"[dim]Disk: ~{need_gb:.1f} GB needed, {free_gb:.0f} GB free[/]")
    return True


async def download_all(acts: list[dict], concurrency: int) -> dict:
    todo = [a for a in acts if not pdf_path(a["celex"]).exists()]
    stats = {"total": len(acts), "skipped": len(acts) - len(todo), "ok": 0, "bytes": 0, "failed": []}
    if not todo:
        return stats

    queue: asyncio.Queue[dict] = asyncio.Queue()
    for act in todo:
        queue.put_nowait(act)

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Downloading PDFs"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TextColumn("· [green]{task.fields[ok]:,} ok[/] · [red]{task.fields[failed]} failed[/]"),
        TextColumn("· [cyan]{task.fields[size]}"),
        TextColumn("· {task.fields[rate]}"),
        TimeElapsedColumn(),
        TextColumn("ETA"),
        TimeRemainingColumn(),
        console=console,
    )
    task = progress.add_task("download", total=len(todo), ok=0, failed=0, size="0 MB", rate="")
    started = time.perf_counter()

    async def worker(client: httpx.AsyncClient) -> None:
        while not queue.empty():
            act = queue.get_nowait()
            size, error = await fetch(client, act)
            if error:
                stats["failed"].append({"celex": act["celex"], "error": error})
            else:
                stats["ok"] += 1
                stats["bytes"] += size
            done = stats["ok"] + len(stats["failed"])
            progress.update(
                task,
                advance=1,
                ok=stats["ok"],
                failed=len(stats["failed"]),
                size=f"{stats['bytes'] / 1024**2:,.0f} MB",
                rate=f"{done / (time.perf_counter() - started):.1f}/s",
            )
            # A short pause per request keeps the load on a public service polite.
            await asyncio.sleep(0.2)

    limits = httpx.Limits(max_connections=concurrency)
    with progress:
        async with httpx.AsyncClient(
            headers=HEADERS, timeout=120, follow_redirects=True, limits=limits
        ) as client:
            await asyncio.gather(*(worker(client) for _ in range(concurrency)))
    return stats


def show_summary(stats: dict, seconds: float) -> None:
    table = Table(title="Download summary", title_style="bold", show_header=False)
    table.add_row("Acts", f"{stats['total']:,}")
    table.add_row("Already on disk (skipped)", f"{stats['skipped']:,}")
    table.add_row("Downloaded now", f"[green]{stats['ok']:,}")
    table.add_row("Failed", f"[red]{len(stats['failed']):,}" if stats["failed"] else "0")
    table.add_row("Size downloaded", f"{stats['bytes'] / 1024**3:.2f} GB")
    table.add_row("Time", time.strftime("%H:%M:%S", time.gmtime(seconds)))
    console.print(table)

    # Rewritten every run, so it only ever lists what is still missing.
    FAILED.unlink(missing_ok=True)
    if stats["failed"]:
        FAILED.write_text("".join(json.dumps(f) + "\n" for f in stats["failed"]))
        reasons = collections.Counter(f["error"].split(":")[0] for f in stats["failed"])
        console.print(f"[yellow]Failures by reason:[/] {dict(reasons.most_common(5))}")
        console.print(f"[yellow]Details in[/] {FAILED.relative_to(ROOT)} [dim](rerun to retry them)[/]")


# --- Entry point --------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--limit", type=int, help="only the first N acts, for testing")
    parser.add_argument("--concurrency", type=int, default=4, help="parallel downloads (default 4)")
    parser.add_argument("--list-only", action="store_true", help="refresh acts.jsonl and stop")
    args = parser.parse_args()

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    console.print(
        Panel.fit(
            "[bold]EU law in force → English PDFs[/]\n"
            f"[dim]Source:[/] EU Publications Office (SPARQL + CELLAR)\n"
            f"[dim]Output:[/] {OUT.relative_to(ROOT)}/\n"
            f"[dim]Parallel downloads:[/] {args.concurrency}"
            + (f"   [dim]Limit:[/] {args.limit}" if args.limit else ""),
            border_style="blue",
        )
    )

    # The list is reused between runs; refreshing it takes a few minutes.
    if args.list_only or not ACTS.exists():
        acts = list_acts()
        ACTS.write_text("".join(json.dumps(a) + "\n" for a in acts))
        console.print(f"[green]✓[/] Saved the list to {ACTS.relative_to(ROOT)}")
    else:
        acts = [json.loads(line) for line in ACTS.read_text().splitlines()]
        console.print(f"[green]✓[/] Loaded {len(acts):,} acts from {ACTS.relative_to(ROOT)}")
    show_list_summary(acts)
    if args.list_only:
        return

    if args.limit:
        acts = acts[: args.limit]
    remaining = sum(1 for a in acts if not pdf_path(a["celex"]).exists())
    if not check_disk(remaining):
        return

    started = time.perf_counter()
    try:
        stats = asyncio.run(download_all(acts, args.concurrency))
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/] Finished files are kept; rerun the same command to continue.")
        return
    show_summary(stats, time.perf_counter() - started)


if __name__ == "__main__":
    main()
