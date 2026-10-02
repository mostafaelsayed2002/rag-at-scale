"""Shared response bodies. Not used by any endpoint yet."""

from pydantic import BaseModel, Field


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
