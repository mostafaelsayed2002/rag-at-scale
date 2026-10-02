"""Data the RAG pipeline produces. No HTTP here: the API schemas reuse these."""

from pydantic import BaseModel


class Citation(BaseModel):
    """One source behind an answer, in the shape the PDF viewer expects."""

    n: int
    chunk_id: int
    doc_id: str
    title: str | None
    page_start: int
    page_end: int
    # The passage itself, so the viewer can find and highlight it in the PDF.
    quote: str
    score: float


class Answer(BaseModel):
    """A generated answer. This is what the cache stores."""

    text: str
    citations: list[Citation]
    tokens_input: int
    tokens_output: int
    # Passages given to the model (usually more than were cited). Stored here
    # so a cached answer can still report it.
    retrieved: int = 0
