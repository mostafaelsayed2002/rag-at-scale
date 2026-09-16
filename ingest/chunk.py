"""Split a document's pages into retrievable chunks.

Chunking streams: pages go in one at a time and chunks come out as soon as
they are final, so memory stays bounded no matter how long the document is.
Chunks still cross page boundaries, because a section that starts on one page
and ends on the next should not be cut at the page break.
"""

from bisect import bisect_right
from collections.abc import Iterable, Iterator

from langchain_text_splitters import RecursiveCharacterTextSplitter
from models import Chunk, Page
from tokenizers import Tokenizer

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"

# Sized with the embedding model's own tokenizer: the model reads at most 512
# tokens and silently drops the rest, so a character-based size can lose text.
TOKENIZER = Tokenizer.from_pretrained(EMBEDDING_MODEL)

CHUNK_TOKENS = 400  # leaves room under 512 for the model's special tokens
OVERLAP_TOKENS = 50

# How much text to hold before splitting. Several chunks' worth, so every
# chunk except the last is final; the last may still grow with the next page.
BUFFER_CHARS = 20_000

# Pages are joined with a single newline. A blank line would tell the splitter
# that every page break is a paragraph break and invite a cut there.
PAGE_JOIN = "\n"


def token_len(text: str) -> int:
    return len(TOKENIZER.encode(text, add_special_tokens=False).ids)


SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_TOKENS,
    chunk_overlap=OVERLAP_TOKENS,
    length_function=token_len,
)


class _PageBuffer:
    """Recent text of one document, plus where each page starts inside it."""

    def __init__(self) -> None:
        self.text = ""
        self.page_starts: list[int] = []
        self.page_numbers: list[int] = []

    def add(self, page: Page) -> None:
        if self.text:
            self.text += PAGE_JOIN
        self.page_starts.append(len(self.text))
        self.page_numbers.append(page.number)
        self.text += page.text

    def page_at(self, position: int) -> int:
        return self.page_numbers[bisect_right(self.page_starts, position) - 1]

    def drop_before(self, position: int) -> None:
        """Forget text before position, keeping the page that contains it."""
        first = bisect_right(self.page_starts, position) - 1
        self.text = self.text[position:]
        self.page_starts = [max(0, s - position) for s in self.page_starts[first:]]
        self.page_numbers = self.page_numbers[first:]


def _locate(text: str, pieces: list[str]) -> list[int]:
    """Start position of each piece in text.

    LangChain's add_start_index is not used: it subtracts the overlap from a
    character count, which is wrong when the overlap is measured in tokens and
    can return another occurrence of the text. Pieces come back in order and
    each starts after the previous one, so searching forward from the previous
    start finds the right occurrence.
    """
    starts, search_from = [], 0
    for piece in pieces:
        start = text.find(piece, search_from)
        if start < 0:
            raise ValueError(f"chunk not found in source text: {piece[:60]!r}")
        starts.append(start)
        search_from = start + 1
    return starts


def chunk_recursive(pages: Iterable[Page]) -> Iterator[Chunk]:
    """Recursive splitting: paragraphs, then lines, then words, then characters."""
    buffer = _PageBuffer()
    doc_id: str | None = None
    index = 0

    def emit(final: bool) -> Iterator[Chunk]:
        nonlocal index
        pieces = SPLITTER.split_text(buffer.text)
        if not pieces:
            return
        starts = _locate(buffer.text, pieces)

        # Unless the document has ended, hold back the last chunk: it ended
        # only because the buffer did, and the next page may extend it.
        ready = len(pieces) if final else len(pieces) - 1
        for piece, start in zip(pieces[:ready], starts[:ready]):
            yield Chunk(
                doc_id=doc_id,
                index=index,
                text=piece,
                page_start=buffer.page_at(start),
                page_end=buffer.page_at(start + len(piece) - 1),
            )
            index += 1

        if not final and ready:
            # Resume from the held-back chunk, so it is re-split together with
            # the text that follows it.
            buffer.drop_before(starts[ready])

    for page in pages:
        if doc_id is None:
            doc_id = page.doc_id
        elif page.doc_id != doc_id:
            raise ValueError(f"pages from two documents: {doc_id} and {page.doc_id}")

        buffer.add(page)
        if len(buffer.text) >= BUFFER_CHARS:
            yield from emit(final=False)

    if doc_id is not None:
        yield from emit(final=True)


if __name__ == "__main__":
    from load import describe, discover, iter_pages

    doc = describe(discover()[0])
    chunks = list(chunk_recursive(iter_pages(doc)))
    print(f"{doc.doc_id}: {len(chunks)} chunks")
    for c in chunks[:3]:
        print(f"\n#{c.index} pages {c.page_start}-{c.page_end}, {token_len(c.text)} tokens")
        print(c.text[:200])
