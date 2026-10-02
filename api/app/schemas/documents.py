"""Response bodies for the /documents endpoints."""

from pydantic import BaseModel


class DocumentSummary(BaseModel):
    """One act in the documents list."""

    doc_id: str
    title: str | None
    collection: str | None
    document_type: str | None
    source_url: str | None
    publication_date: str | None
    page_count: int | None
    chunk_count: int | None


class CollectionCount(BaseModel):
    name: str
    count: int


class CorpusSize(BaseModel):
    documents: int
    chunks: int


class DocumentPage(BaseModel):
    """Response model for GET /documents: one page of the matching acts.

    The corpus holds tens of thousands of acts (~19 MB as one list), so the
    list is searched and paged on the server instead of sent whole.
    """

    total: int  # acts matching the search, across all pages
    items: list[DocumentSummary]
    # Over the whole corpus, not the search, so filter buttons show fixed counts.
    collections: list[CollectionCount]
    corpus: CorpusSize


class Document(DocumentSummary):
    """Response model for GET /documents/{doc_id}."""

    source_organization: str | None
    celex_number: str | None
    topics: list[str]  # EUROVOC subjects, e.g. ["data protection", "personal data"]
    has_file: bool
