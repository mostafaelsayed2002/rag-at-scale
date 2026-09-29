"""Response bodies for the /documents endpoints."""

from pydantic import BaseModel


class DocumentSummary(BaseModel):
    """Response model for GET /documents."""

    doc_id: str
    title: str | None
    collection: str | None
    document_type: str | None
    source_url: str | None
    page_count: int | None
    chunk_count: int | None


class Document(DocumentSummary):
    """Response model for GET /documents/{doc_id}."""

    source_organization: str | None
    celex_number: str | None
    publication_date: str | None
    topics: list[str]  # EUROVOC subjects, e.g. ["data protection", "personal data"]
    has_file: bool
