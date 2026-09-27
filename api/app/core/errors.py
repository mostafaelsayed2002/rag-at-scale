"""Domain errors, and the one place that turns them into HTTP responses.

The RAG code raises these without knowing about HTTP; the handler below maps
them to status codes, so routes do not repeat the same try/except.
"""

import logging
from typing import ClassVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


class QuotaExhausted(Exception):
    """Gemini refused a call because the quota is used up."""

    MESSAGES: ClassVar[dict[str, str]] = {
        "embedding": "The embedding quota is used up, so chat is unavailable right now.",
        "generation": "The model quota is used up, so answering is unavailable right now.",
    }

    def __init__(self, step: str, message: str):
        super().__init__(message)
        self.step = step  # "embedding" or "generation"

    @property
    def detail(self) -> str:
        return self.MESSAGES[self.step]


def is_quota_error(exc: Exception) -> bool:
    """Gemini reports an exhausted quota as RESOURCE_EXHAUSTED / HTTP 429."""
    message = str(exc)
    return "RESOURCE_EXHAUSTED" in message or "429" in message


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RateLimitExceeded)
    async def rate_limited(request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": f"Too many questions (limit {exc.detail}). Please wait a moment."},
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(QuotaExhausted)
    async def quota_exhausted(request: Request, exc: QuotaExhausted) -> JSONResponse:
        logger.warning("%s quota exhausted: %s", exc.step, exc)
        # Same {"detail": ...} shape as HTTPException, which the frontend reads.
        return JSONResponse(status_code=429, content={"detail": exc.detail})
