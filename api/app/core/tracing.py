"""LangSmith tracing: which passages, prompt and answer each chat produced.

The SDK reads only os.environ, while pydantic-settings keeps .env values in
`settings`, so configure() copies them over. Call it first at startup: the SDK
caches the first value it reads. A LangSmith outage never fails a request.
"""

import logging
import os

from .config import settings

logger = logging.getLogger(__name__)


def configure() -> bool:
    """Copy the LangSmith settings into os.environ. Returns whether tracing is on."""
    enabled = settings.langsmith_tracing and bool(settings.langsmith_api_key)
    os.environ["LANGSMITH_TRACING"] = "true" if enabled else "false"
    if not enabled:
        logger.info("LangSmith tracing off")
        return False
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    logger.info("LangSmith tracing on, project %s", settings.langsmith_project)
    return True
