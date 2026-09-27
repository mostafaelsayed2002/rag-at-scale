"""Logging, and one request_log row per chat request for the analytics page.

Monitoring never fails a request: errors are logged and ignored.
"""

import json
import logging
from datetime import datetime, timezone

from psycopg import Error as PsycopgError
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)

class JSONFormatter(logging.Formatter):
    """Writes each log line as JSON, so log tools can filter by field."""

    def format(self, record: logging.LogRecord) -> str:

        payload = dict(getattr(record, "extra_data", {}))
        payload.update(
            {
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
            }
        )
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", as_json: bool = True) -> None:
    """Set up app-wide logging. Replaces old handlers, so lines never print twice."""

    handler = logging.StreamHandler()
    handler.setFormatter(
        JSONFormatter() if as_json else logging.Formatter("%(levelname)-7s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


async def record_chat(
    pool,
    *,
    query: str,
    latency_ms: float,
    status: int,
    cache_hit: bool,
    tokens_input: int,
    tokens_output: int,
    stages: dict[str, float],
) -> None:
    """Append one chat request to request_log, the history the analytics page reads."""
    row = {
        "query": query,
        "status_code": status,
        "latency_ms": round(latency_ms, 2),
        "cache_hit": cache_hit,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "error": None if status < 400 else f"HTTP {status}",
        # e.g. {"embedding": 41.2, "retrieval": 8.9, "generation": 1980.0}
        "stages": Jsonb(stages) if stages else None,
    }
    try:
        async with pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO request_log
                    (query, status_code, latency_ms, cache_hit,
                     tokens_input, tokens_output, error, stages)
                VALUES (%(query)s, %(status_code)s, %(latency_ms)s,
                        %(cache_hit)s, %(tokens_input)s, %(tokens_output)s,
                        %(error)s, %(stages)s)
                """,
                row,
            )
    except PsycopgError as exc:
        # A full disk or a missing migration must not fail a working chat.
        logger.warning("could not write request_log: %s", exc)
