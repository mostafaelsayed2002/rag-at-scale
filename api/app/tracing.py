"""Send traces to LangSmith, when it is switched on.

The dashboard says an answer took 30 seconds. A trace says which prompt took
30 seconds, what came back, and which passages were in front of the model —
which is how you tell a retrieval problem from a prompting one.

Nothing here changes behaviour when tracing is off, and a failure to reach
LangSmith never fails a request: the SDK batches in the background.
"""

import logging
import os

from .config import settings

logger = logging.getLogger(__name__)


def configure() -> bool:
    """Put the LangSmith settings into the environment, where the SDK looks.

    This is the whole reason this function exists. pydantic-settings reads
    .env into the Settings object, not into os.environ, and the LangSmith
    client only reads os.environ. Set them in .env alone and tracing silently
    does nothing — the same trap the Gemini key fell into.
    """
    if not settings.langsmith_tracing:
        # Explicitly off, in case the environment says otherwise: the setting
        # is the single source of truth.
        os.environ["LANGSMITH_TRACING"] = "false"
        logger.info("LangSmith tracing disabled")
        return False

    if not settings.langsmith_api_key:
        logger.warning("LANGSMITH_TRACING is on but no API key is set; tracing stays off")
        os.environ["LANGSMITH_TRACING"] = "false"
        return False

    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
    os.environ["LANGSMITH_ENDPOINT"] = settings.langsmith_endpoint
    logger.info(
        "LangSmith tracing enabled, project %s at %s",
        settings.langsmith_project,
        settings.langsmith_endpoint,
    )
    return True
