"""Split a document into overlapping chunks."""

from bisect import bisect_right
from pathlib import Path

import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models import Chunk

# Measured in characters. Gemini reads up to 8,192 tokens, roughly 30,000
# characters, so size is a retrieval choice rather than a model limit: small
# enough to be about one idea, large enough to answer a question.
# Week 3 benchmarks this against other strategies and sizes.
CHUNK_CHARS = 1600
OVERLAP_CHARS = 200

# Pages are joined with a single newline. A blank line would tell the splitter
# that every page break is a paragraph break and invite a cut there, splitting
# articles that run across two pages.
PAGE_JOIN = "\n"

SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_CHARS,
    chunk_overlap=OVERLAP_CHARS,
    add_start_index=True,  # where each chunk starts, needed to find its pages
)


def chunking(document: pymupdf.Document) -> list[Chunk]:
    """Chunk one open PDF, recording the page range each chunk covers."""
    doc_id = Path(document.name).stem

    # Join the pages into one text, remembering where each page begins, so a
    # chunk that crosses a page break can still report both page numbers.
    texts: list[str] = []
    starts: list[int] = []
    numbers: list[int] = []
    offset = 0
    for page in document:
        text = page.get_text()
        if not text.strip():
            continue
        texts.append(text)
        starts.append(offset)
        numbers.append(page.number + 1)  # page.number counts from 0
        offset += len(text) + len(PAGE_JOIN)

    if not texts:
        return []
    full = PAGE_JOIN.join(texts)

    def page_at(position: int) -> int:
        return numbers[bisect_right(starts, position) - 1]

    chunks = []
    for index, piece in enumerate(SPLITTER.create_documents([full])):
        start = piece.metadata["start_index"]
        end = start + len(piece.page_content) - 1
        chunks.append(
            Chunk(
                doc_id=doc_id,
                index=index,
                text=piece.page_content,
                page_start=page_at(start),
                page_end=page_at(end),
            )
        )
    return chunks


if __name__ == "__main__":
    from load import load_pdfs

    document = load_pdfs()[0]
    chunks = chunking(document)
    print(f"{Path(document.name).stem}: {len(chunks)} chunks")
    for c in chunks[:3]:
        print(f"\n#{c.index} pages {c.page_start}-{c.page_end}, {len(c.text)} chars")
        print(" ".join(c.text.split())[:180])
