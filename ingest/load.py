"""Load PDFs"""

from pathlib import Path

import pymupdf


def load_pdfs(data_dir: str = "../data") -> list[pymupdf.Document]:
    data_path = Path(data_dir)
    if not data_path.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_path.resolve()}")

    documents = []
    for pdf in sorted(data_path.rglob("*.pdf")):
        try:
            document = pymupdf.open(pdf)
        except (OSError, pymupdf.MuPDFError) as exc:
            print(f"skipped {pdf}: {exc}")
            continue
        documents.append(document)
    return documents


if __name__ == "__main__":
    print(load_pdfs())
