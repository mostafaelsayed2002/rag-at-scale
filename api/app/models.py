from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""

    query: str = Field(
        ..., description="The user's query to the chatbot.", min_length=1, max_length=1000
    )
    user_id: str = Field(..., description="The unique identifier for the user.")
    thread_id: str = Field(..., description="The unique identifier for the conversation thread.")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="The timestamp of the request.",
    )


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""

    response: str = Field(..., description="The chatbot's response to the user's query.")

    thread_id: str = Field(..., description="The unique identifier for the conversation thread.")
    model_used: str = Field(..., description="The model used to generate the response.")
    cashed: bool = Field(..., description="Indicates if the response was retrieved from cache.")
    processing_time: float = Field(
        ..., description="The time taken to process the request in seconds."
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="The timestamp of the response.",
    )


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

    status: str = Field(..., description="The status of the application.")
    environment: str = Field(..., description="The current environment of the application.")
    version: str = "0.1.0"
    checks: dict = {}


class MatricsResponse(BaseModel):
    """Response model for metrics endpoint."""

    total_requests: int
    total_errors: int
    error_rate: float
    avg_latency_ms: float
    cache_hit_rate: float
    total_input_tokens: int
    total_output_tokens: int


class ErrorResponse(BaseModel):
    """Response model for error responses."""

    error: str = Field(..., description="The error message.")
    deitails: str | None = None
    request_id: str | None = None
