"""One request_log row per chat request, the history the analytics page reads.

Logging never fails a request: database errors are logged and ignored.
"""

import logging

from psycopg import Error as PsycopgError
from psycopg.types.json import Jsonb

logger = logging.getLogger(__name__)


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
    """Append one chat request to request_log."""
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
