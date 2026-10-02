"""Plain data passed between pipeline stages.

They hold only strings, numbers and lists, so they cross process boundaries
unchanged and serialise straight to JSON for the shard files.
"""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True, slots=True)
class Page:
    """One page of cleaned text."""

    number: int  # 1-based, as a reader would cite it
    text: str


@dataclass(slots=True)
class Chunk:
    """A retrievable passage. It can span pages, so it records both ends."""

    doc_id: str
    index: int  # position within the document, for stable ordering
    text: str
    page_start: int
    page_end: int
    tokens: int = 0  # as the embedding model counts them

    def to_json(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class DocumentInfo:
    """One act: its metadata from acts.jsonl plus what parsing found."""

    doc_id: str  # the CELEX number, e.g. 32016R0679
    path: str  # absolute, so a worker process can open it from anywhere
    title: str | None = None
    act_type: str | None = None  # REG, DIR, DEC, REG_IMPL...
    date: str | None = None
    topics: list[str] = field(default_factory=list)
    sha256: str = ""  # content hash: the resume key, unchanged by renames
    page_count: int = 0
    chunk_count: int = 0
    status: str = "ok"  # or why it was skipped: "no_text", "garbled", "unreadable"

    def to_json(self) -> dict:
        return asdict(self)
