"""Download the English HTML of every act in the corpus from CELLAR.

    uv run --package rag-ingest python ingest/download_html.py               # everything
    uv run --package rag-ingest python ingest/download_html.py --limit 50    # a quick test

The HTML is what the chunker reads: since the 2000s most acts come as tagged
XHTML, where articles, recitals, chapters and annexes are marked
(id="art_33", id="rct_85", id="cpt_IV.sct_2"). Older acts come as plain HTML:
clean typed text, one paragraph per <p>, without the PDF's OCR errors and
mixed-up columns. About 7% of acts (mostly recent merger and State aid
decisions) have no HTML at all and keep the PDF route.

Two steps:
1. One catalogue query per 100 acts asks which formats exist in English
   (xhtml, html, pdf...). Saved to data/eurlex/formats.json and reused.
2. Each act is fetched from CELLAR by content negotiation: Accept
   application/xhtml+xml for tagged acts, text/html for the plain ones. The
   EUR-Lex website itself blocks automated downloads; CELLAR is the
   Publications Office's machine-access route.

Safe to stop and rerun: finished files are skipped, and a file only gets its
final name once it is complete.
"""

import argparse
import csv
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from tqdm import tqdm

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "eurlex"
HTML_DIR = OUT / "html"
ACTS = OUT / "acts.jsonl"
FORMATS = OUT / "formats.json"
FAILED = OUT / "html_failed.jsonl"

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
CELLAR = "http://publications.europa.eu/resource/celex/{}"
HEADERS = {"User-Agent": "rag-at-scale/0.1 (portfolio research project)"}

# Every format of the act's English version, by CELEX number. Matching the
# CELEX number as a typed value (not a string filter) keeps a 100-act query
# under a second.
FORMATS_QUERY = """PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
SELECT ?celex (GROUP_CONCAT(DISTINCT STR(?type); separator=",") AS ?types) WHERE {
  VALUES ?celex { %s }
  ?work cdm:resource_legal_id_celex ?celex .
  ?expr cdm:expression_belongs_to_work ?work ;
        cdm:expression_uses_language <http://publications.europa.eu/resource/authority/language/ENG> .
  ?man cdm:manifestation_manifests_expression ?expr ;
       cdm:manifestation_type ?type .
} GROUP BY ?celex"""


def read_acts() -> list[str]:
    """CELEX numbers of the acts in the corpus (from download.py's list)."""
    celexes = []
    with ACTS.open() as f:
        for line in f:
            celexes.append(json.loads(line)["celex"])
    return celexes


def post_with_retries(data: dict) -> httpx.Response:
    """A catalogue query, retried a few times: the endpoint sometimes times out."""
    for attempt in range(4):
        try:
            response = httpx.post(
                SPARQL, data=data, headers={**HEADERS, "Accept": "text/csv"}, timeout=180
            )
            response.raise_for_status()
            return response
        except httpx.HTTPError:
            if attempt == 3:
                raise
            time.sleep(10)


def load_formats(celexes: list[str]) -> dict[str, list[str]]:
    """Which formats exist for each act, from the saved file or the catalogue."""
    formats = json.loads(FORMATS.read_text()) if FORMATS.exists() else {}
    todo = [c for c in celexes if c not in formats]
    for start in tqdm(range(0, len(todo), 100), desc="catalogue", disable=not todo):
        batch = todo[start : start + 100]
        values = " ".join(f'"{c}"^^xsd:string' for c in batch)
        response = post_with_retries({"query": FORMATS_QUERY % values})
        for row in csv.DictReader(io.StringIO(response.text)):
            formats[row["celex"]] = row["types"].split(",") if row["types"] else []
        for celex in batch:
            formats.setdefault(celex, [])  # nothing in English
        FORMATS.write_text(json.dumps(formats))
    return formats


def html_kind(types: list[str]) -> str | None:
    """'xhtml' (tagged), 'html' (plain) or None (no HTML: PDF only)."""
    if "xhtml" in types:
        return "xhtml"
    if "html" in types:
        return "html"
    return None


def target(celex: str, kind: str) -> Path:
    return HTML_DIR / f"{celex}.{kind}"


def fetch(job: tuple[str, str]) -> dict | None:
    """Download one act's HTML. Returns a failure record, or None on success."""
    celex, kind = job
    path = target(celex, kind)
    accept = "application/xhtml+xml" if kind == "xhtml" else "text/html"
    headers = {**HEADERS, "Accept": accept, "Accept-Language": "eng"}
    # CELEX numbers like 31958D1006(01) need their brackets encoded, or CELLAR answers 404.
    url = CELLAR.format(celex.replace("(", "%28").replace(")", "%29"))
    for attempt in range(3):
        try:
            response = httpx.get(url, headers=headers, follow_redirects=True, timeout=180)
            break
        except httpx.HTTPError as error:
            if attempt == 2:
                return {"celex": celex, "kind": kind, "error": type(error).__name__}
            time.sleep(5)
    if response.status_code != 200:
        return {"celex": celex, "kind": kind, "status": response.status_code}
    partial = path.with_suffix(path.suffix + ".part")
    partial.write_bytes(response.content)
    partial.rename(path)  # only a complete file gets the final name
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, help="only the first N acts, for testing")
    parser.add_argument("--workers", type=int, default=4, help="downloads at the same time")
    args = parser.parse_args()

    celexes = read_acts()
    formats = load_formats(celexes)
    HTML_DIR.mkdir(parents=True, exist_ok=True)

    jobs = []
    no_html = 0
    for celex in celexes:
        kind = html_kind(formats.get(celex, []))
        if kind is None:
            no_html += 1
        elif not target(celex, kind).exists():
            jobs.append((celex, kind))
    if args.limit:
        jobs = jobs[: args.limit]
    print(f"{len(celexes):,} acts: {no_html:,} have no HTML, {len(jobs):,} to download")

    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for failure in tqdm(pool.map(fetch, jobs), total=len(jobs), desc="html"):
            if failure:
                failures.append(failure)
    with FAILED.open("w") as f:
        for failure in failures:
            f.write(json.dumps(failure) + "\n")
    print(f"done: {len(jobs) - len(failures):,} downloaded, {len(failures):,} failed (see {FAILED.name})")


if __name__ == "__main__":
    main()
