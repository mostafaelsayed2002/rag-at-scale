"""Split a document's pages into overlapping chunks that fit the embedding model."""

from bisect import bisect_right
from functools import lru_cache

from config import settings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from models import Chunk, Page
from tokenizers import Tokenizer

# Pages are joined with a single newline. A blank line would tell the splitter
# that every page break is a paragraph break and invite a cut there, splitting
# articles that run across two pages.
PAGE_JOIN = "\n"


@lru_cache(maxsize=1)
def splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_chars,
        chunk_overlap=settings.overlap_chars,
        add_start_index=True,  # where each chunk starts, needed to find its pages
    )


def tokenizer_file() -> str:
    """Download the tokenizer once and return its local path. Worker processes
    load it from this file: fetching it from the Hub in each of them was the
    slowest part of chunking."""
    from huggingface_hub import hf_hub_download

    return hf_hub_download(settings.embedding_model, "tokenizer.json")


# Set in each worker process by use_tokenizer_file() before any chunking.
TOKENIZER_FILE: str | None = None


def use_tokenizer_file(path: str) -> None:
    global TOKENIZER_FILE
    TOKENIZER_FILE = path


@lru_cache(maxsize=1)
def tokenizer() -> Tokenizer:
    """The embedding model's own tokenizer, without its 512-token cut-off, so an
    over-long chunk shows up as over-long instead of silently shortened."""
    tok = Tokenizer.from_file(TOKENIZER_FILE or tokenizer_file())
    tok.no_truncation()
    tok.no_padding()
    return tok


def count_tokens(texts: list[str]) -> list[int]:
    return [len(e.ids) for e in tokenizer().encode_batch(texts)]


def fit(text: str) -> list[str]:
    """Split text again, in halves, until every piece fits the model."""
    if count_tokens([text])[0] <= settings.max_tokens:
        return [text]
    half = RecursiveCharacterTextSplitter(
        chunk_size=max(len(text) // 2, 200), chunk_overlap=0
    ).split_text(text)
    if len(half) < 2:  # cannot split further (one enormous "word"); keep it
        return [text]
    return [piece for part in half for piece in fit(part)]


def chunk_pages(doc_id: str, pages: list[Page]) -> list[Chunk]:
    """Chunk a document, recording the page range each chunk covers."""
    if not pages:
        return []

    # Join the pages into one text, remembering where each page begins, so a
    # chunk that crosses a page break can still report both page numbers.
    starts, offset = [], 0
    for page in pages:
        starts.append(offset)
        offset += len(page.text) + len(PAGE_JOIN)
    full = PAGE_JOIN.join(p.text for p in pages)

    def page_at(position: int) -> int:
        return pages[bisect_right(starts, position) - 1].number

    pieces: list[tuple[str, int, int]] = []
    for doc in splitter().create_documents([full]):
        start = doc.metadata["start_index"]
        first, last = page_at(start), page_at(start + len(doc.page_content) - 1)
        # Tables of numbers tokenise far denser than prose: those chunks are
        # split again so the model does not silently drop their ends.
        for text in fit(doc.page_content):
            pieces.append((text, first, last))

    tokens = count_tokens([text for text, _, _ in pieces])
    return [
        Chunk(doc_id=doc_id, index=i, text=text, page_start=first, page_end=last, tokens=n)
        for i, ((text, first, last), n) in enumerate(zip(pieces, tokens, strict=True))
    ]
