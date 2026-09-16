"""Plain data passed between pipeline stages.

Every stage takes and returns these types and nothing else. They hold only
strings, numbers and lists, so they can cross process boundaries unchanged,
which is what lets the orchestrator run stages in parallel later.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Page:
    """One page of extracted text."""

    doc_id: str
    number: int  # 1-based, as a reader would cite it
    text: str


@dataclass(frozen=True, slots=True)
class Chunk:
    """A retrievable passage. It can span pages, so it records both ends."""

    doc_id: str
    index: int  # position within the document, for stable ordering and ids
    text: str
    page_start: int
    page_end: int
    section: str | None = None


@dataclass(frozen=True, slots=True)
class DocumentInfo:
    """What the pipeline needs to know about a file before reading it."""

    doc_id: str
    path: str  # absolute, so a worker process can open it from anywhere
    sha256: str  # content hash: the checkpoint key, unchanged by renames
    page_count: int
    title: str | None = None
    source_url: str | None = None
    # Filterable fields from the corpus metadata: organisation, type, date.
    extra: dict[str, object] = field(default_factory=dict)
