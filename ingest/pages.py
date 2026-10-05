"""Find the PDF page(s) of every chunk, so citations can open the PDF at the
right page and highlight the passage.

Chunks made from HTML (html_chunk.py) have no page numbers: HTML has no pages.
The wording is the same as in the PDF, so each chunk's text is looked up in its
act's PDF, once, and the result saved to a JSON file:

    {"32016R0679": [[1, 1], [1, 2], ..., [52, 52], ...], ...}

one [page_start, page_end] per chunk, in chunk order; [0, 0] when not found.

Self-contained (only PyMuPDF), so it runs where the PDFs are, e.g. on the server:

    python pages.py --chunks work/chunks --pdf data/eurlex/pdf --out pages.json

Text is compared as lowercase letters and digits only, so line breaks,
hyphenation and spacing differences between HTML and PDF do not matter.
"""

import argparse
import gzip
import json
import re
import time
from bisect import bisect_right
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

PROBE = 50  # letters per probe: long enough to be unique on a page


def letters(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def read_chunks(chunks_dir: Path) -> dict[str, list[str]]:
    """Every act's chunk bodies (without the header line), in chunk order."""
    acts: dict[str, list[tuple[int, str]]] = {}
    for path in sorted(chunks_dir.glob("shard-*.chunks.jsonl*")):
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8") as f:
            for line in f:
                chunk = json.loads(line)
                body = chunk["text"].split("\n", 1)[-1]
                acts.setdefault(chunk["doc_id"], []).append((chunk["index"], body))
    return {doc: [body for _, body in sorted(chunks)] for doc, chunks in acts.items()}


def probes(text: str) -> list[str]:
    """A few PROBE-long pieces of the text: near the start, the middle and the end.
    Several, because a heading or footnote can sit between PDF lines."""
    if len(text) <= PROBE:
        return [text] if text else []
    starts = [0, len(text) // 4, len(text) // 2, 3 * len(text) // 4, len(text) - PROBE]
    return [text[s : s + PROBE] for s in starts]


def locate(job: tuple[str, list[str], str]) -> tuple[str, list[list[int]]]:
    """The [page_start, page_end] of each chunk of one act."""
    import pymupdf

    doc_id, bodies, pdf_dir = job
    pdf = Path(pdf_dir) / f"{doc_id}.pdf"
    if not pdf.exists():
        return doc_id, [[0, 0] for _ in bodies]

    # The whole PDF as one letters-only string, remembering where each page starts.
    starts = []
    parts = []
    offset = 0
    try:
        with pymupdf.open(pdf) as document:
            for page in document:
                text = letters(page.get_text())
                starts.append(offset)
                parts.append(text)
                offset += len(text)
    except Exception:
        return doc_id, [[0, 0] for _ in bodies]
    full = "".join(parts)

    def page_at(position: int) -> int:
        return bisect_right(starts, position)  # 1-based page number

    result = []
    cursor = 0  # chunks follow the PDF's order, so search on from the last hit
    for body in bodies:
        found = []
        for probe in probes(letters(body)):
            at = full.find(probe, cursor)
            if at < 0:
                at = full.find(probe)  # out of order (e.g. a jumbled old scan)
            if at >= 0:
                found.append(at)
        if found:
            result.append([page_at(min(found)), page_at(max(found) + PROBE - 1)])
            cursor = min(found)
        else:
            result.append([0, 0])
    return doc_id, result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--chunks", type=Path, required=True, help="folder with shard-*.chunks.jsonl(.gz)")
    parser.add_argument("--pdf", type=Path, required=True, help="folder with <CELEX>.pdf")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    acts = read_chunks(args.chunks)
    print(f"{len(acts):,} acts, {sum(len(b) for b in acts.values()):,} chunks", flush=True)
    jobs = [(doc, bodies, str(args.pdf)) for doc, bodies in acts.items()]
    pages = {}
    found = 0
    total = 0
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i, (doc, result) in enumerate(pool.map(locate, jobs, chunksize=16), start=1):
            pages[doc] = result
            found += sum(1 for p in result if p[0] > 0)
            total += len(result)
            if i % 1000 == 0 or i == len(jobs):
                rate = i / (time.perf_counter() - started)
                print(f"{i:,}/{len(jobs):,} acts · {found / total:.1%} of chunks placed · "
                      f"~{(len(jobs) - i) / rate / 60:.0f} min left", flush=True)
    args.out.write_text(json.dumps(pages))
    print(f"done: {found:,} of {total:,} chunks placed ({found / total:.1%}) -> {args.out}", flush=True)


if __name__ == "__main__":
    main()
