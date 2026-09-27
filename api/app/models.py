from datetime import datetime, timezone

from pydantic import BaseModel, Field

from .llm import Citation


def _now() -> datetime:
    """Timezone-aware UTC. utcnow() returns a naive value and is deprecated."""
    return datetime.now(tz=timezone.utc)


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    query: str = Field(
        ..., description="The user's query to the chatbot.", min_length=1, max_length=1000
    )
    user_id: str = Field(default="anonymous", description="The unique identifier for the user.")
    thread_id: str = Field(
        default="default",
        description="Conversation thread. Recorded, but answers are single-turn for now.",
    )
    timestamp: datetime = Field(
        default_factory=_now,
        description="The timestamp of the request.",
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    response: str = Field(..., description="The chatbot's response to the user's query.")
    citations: list[Citation] = Field(
        default_factory=list,
        description="The passages behind the answer, in the order first cited.",
    )
    thread_id: str = Field(..., description="The unique identifier for the conversation thread.")
    model_used: str = Field(..., description="The model used to generate the response.")
    cached: bool = Field(..., description="Indicates if the response was retrieved from cache.")
    retrieved_chunks: int = Field(
        default=0, description="Passages retrieved and put in front of the model."
    )
    # Reported by the API, not estimated, so the cost shown to the user is real.
    tokens_input: int = Field(default=0, description="Prompt tokens the answer cost.")
    tokens_output: int = Field(default=0, description="Completion tokens the answer cost.")
    processing_time: float = Field(
        ..., description="The time taken to process the request in seconds."
    )
    timestamp: datetime = Field(
        default_factory=_now,
        description="The timestamp of the response.",
    )


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
    has_file: bool


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = Field(..., description="The status of the application.")
    environment: str = Field(..., description="The current environment of the application.")
    version: str = "0.1.0"
    checks: dict = {}


class ErrorResponse(BaseModel):
    """Response model for error responses."""

    error: str = Field(..., description="The error message.")
    deitails: str | None = None
    request_id: str | None = None
