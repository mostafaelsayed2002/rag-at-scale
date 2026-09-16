"""Read PDFs from the corpus, one page at a time.

Functions here take a file path rather than an open document: a worker process
receives the path and opens the file itself, because an open PDF cannot be
sent between processes.

PyMuPDF rather than pypdf: pypdf split words apart in 9 of the 15 CJEU
judgments ("t he", "wit h"), and PyMuPDF reads the whole corpus cleanly and
about nine times faster. It is AGPL-licensed, which is fine while the
repository is public.
"""

import hashlib
from collections.abc import Iterator
from pathlib import Path

import pymupdf
from models import DocumentInfo, Page

# Anchored to this file, so it works whether you run from ingest/ or the root.
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class LoadError(Exception):
    """A PDF that could not be opened or read."""


def discover(data_dir: Path = DEFAULT_DATA_DIR) -> list[Path]:
    """Every PDF under the corpus folder, in a stable order."""
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir.resolve()}")
    return sorted(p for p in data_dir.rglob("*.pdf") if not p.name.startswith("."))


def doc_id_for(path: Path, data_dir: Path = DEFAULT_DATA_DIR) -> str:
    """The path inside the corpus without its extension.

    data/legislation/gdpr/gdpr_consolidated__consolidated.pdf
    -> legislation/gdpr/gdpr_consolidated__consolidated
    """
    return path.resolve().relative_to(data_dir.resolve()).with_suffix("").as_posix()


def file_sha256(path: Path) -> str:
    """Content hash, read in 1 MB blocks so large files don't fill memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _open(path: Path) -> pymupdf.Document:
    try:
        return pymupdf.open(path)
    except (RuntimeError, OSError, ValueError) as exc:
        raise LoadError(f"{path}: {exc}") from exc


def describe(path: Path, data_dir: Path = DEFAULT_DATA_DIR) -> DocumentInfo:
    """Identity and size of a document, without extracting any text."""
    with _open(path) as pdf:
        page_count = pdf.page_count
    return DocumentInfo(
        doc_id=doc_id_for(path, data_dir),
        path=str(path.resolve()),
        sha256=file_sha256(path),
        page_count=page_count,
    )


def iter_pages(doc: DocumentInfo) -> Iterator[Page]:
    """Yield pages lazily, so a long document is never all in memory at once.

    Blank pages, usually scans or separators, are skipped. Page numbers still
    come from each page's real position, so citations stay correct.
    """
    with _open(Path(doc.path)) as pdf:
        for number, page in enumerate(pdf, start=1):
            try:
                text = page.get_text()
            except RuntimeError as exc:
                raise LoadError(f"{doc.path} page {number}: {exc}") from exc
            if text.strip():
                yield Page(doc_id=doc.doc_id, number=number, text=text)


if __name__ == "__main__":
    paths = discover()
    print(f"{len(paths)} PDFs found")
    doc = describe(paths[0])
    pages = list(iter_pages(doc))
    print(f"{doc.doc_id}: {doc.page_count} pages, {len(pages)} with text")
    print(pages[0].text[:300])
