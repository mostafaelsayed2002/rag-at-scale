"""Structured logs, shared counters, and a durable record of every request.

Two stores, because they answer different questions. Redis holds the running
counters: what is happening right now, incremented atomically so several
workers agree on one number. Postgres holds one row per request: what has
happened over time, which is the only way to get a percentile or a trend,
since a counter has already thrown the individual measurements away.

Neither is allowed to fail a request. Monitoring that can take the service
down is worse than no monitoring.
"""

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import Request
from psycopg import Error as PsycopgError
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# Same versioning idea as the cache: a new prefix starts the counts over
# rather than mixing them with numbers that meant something else.
PREFIX = "rag:v1:metrics"


class JSONFormatter(logging.Formatter):
    """One JSON object per line, so a log collector can read the fields.

    Plain text logs have to be parsed with regular expressions to answer
    "which requests were slow"; these can be queried directly.
    """

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Anything passed as logger.info(..., extra={"extra_data": {...}}).
        payload.update(getattr(record, "extra_data", {}))
        return json.dumps(payload)


def setup_logging(level: str = "INFO", as_json: bool = True) -> None:
    """Configure the root logger once.

    Handlers are replaced rather than appended: adding one on every call is
    how a log line ends up printed twice, then three times.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(
        JSONFormatter() if as_json else logging.Formatter("%(levelname)-7s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


class Metrics:
    """Counters in Redis, shared by every worker and every container.

    The counting happens inside Redis, so `INCR` from two workers at the same
    instant cannot lose one the way `self.total += 1` can. A dict in the
    process would report only the requests that one worker happened to serve.
    """

    FIELDS = (
        "requests_total",
        "errors_total",
        "cache_hits",
        "cache_misses",
        "tokens_input",
        "tokens_output",
    )

    def __init__(self, client: Redis | None):
        self.client = client

    async def record(
        self,
        latency_ms: float,
        *,
        error: bool = False,
        # None means this endpoint never consults the cache, so the request
        # is neither a hit nor a miss. Counting it as a miss would make the
        # hit rate depend on how much unrelated traffic there was.
        cache_hit: bool | None = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None:
        if self.client is None:
            return
        try:
            # A pipeline sends every increment in one round trip instead of
            # six, so measuring a request costs about as much as one command.
            pipe = self.client.pipeline()
            pipe.incr(f"{PREFIX}:requests_total")
            pipe.incrbyfloat(f"{PREFIX}:latency_sum", latency_ms)
            if cache_hit is not None:
                pipe.incr(f"{PREFIX}:cache_hits" if cache_hit else f"{PREFIX}:cache_misses")
            if error:
                pipe.incr(f"{PREFIX}:errors_total")
            if tokens_input:
                pipe.incrby(f"{PREFIX}:tokens_input", tokens_input)
            if tokens_output:
                pipe.incrby(f"{PREFIX}:tokens_output", tokens_output)
            await pipe.execute()
        except RedisError as exc:
            logger.warning("could not record metrics: %s", exc)

    async def summary(self) -> dict:
        """The numbers behind /metrics, as rates rather than raw totals."""
        values = dict.fromkeys(self.FIELDS, 0)
        latency_sum = 0.0

        if self.client is not None:
            try:
                keys = [f"{PREFIX}:{name}" for name in self.FIELDS]
                raw = await self.client.mget([*keys, f"{PREFIX}:latency_sum"])
                values = {name: int(raw[i] or 0) for i, name in enumerate(self.FIELDS)}
                latency_sum = float(raw[-1] or 0.0)
            except RedisError as exc:
                logger.warning("could not read metrics: %s", exc)

        requests = values["requests_total"]
        lookups = values["cache_hits"] + values["cache_misses"]
        return {
            "total_requests": requests,
            "total_errors": values["errors_total"],
            # Guarded: the first call to /metrics happens with zero requests
            # recorded, and dividing there would be the only way this endpoint
            # could fail.
            "error_rate": round(values["errors_total"] / requests, 4) if requests else 0.0,
            "avg_latency_ms": round(latency_sum / requests, 2) if requests else 0.0,
            "cache_hit_rate": round(values["cache_hits"] / lookups, 4) if lookups else 0.0,
            "total_input_tokens": values["tokens_input"],
            "total_output_tokens": values["tokens_output"],
        }


async def log_request(pool, **row) -> None:
    """Append one row to request_log, the history the analytics page reads."""
    try:
        async with pool.connection() as conn:
            await conn.execute(
                """
                INSERT INTO request_log
                    (path, query, status_code, latency_ms, cache_hit,
                     tokens_input, tokens_output, error)
                VALUES (%(path)s, %(query)s, %(status_code)s, %(latency_ms)s,
                        %(cache_hit)s, %(tokens_input)s, %(tokens_output)s, %(error)s)
                """,
                row,
            )
    except PsycopgError as exc:
        # A full disk or a missing migration must not turn a working search
        # into a 500. The counters in Redis still have the request.
        logger.warning("could not write request_log: %s", exc)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Time every request, not just the ones that call a model.

    Middleware sees the whole request, so latency here is what the user
    actually waited, including the database and serialisation.
    """

    # Measuring the metrics endpoint with itself makes the numbers report on
    # the act of reading them; health checks would drown everything else.
    SKIP = {"/metrics", "/health", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.SKIP:
            return await call_next(request)

        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            # Endpoints set these; a request that failed before reaching one
            # simply has the defaults.
            state = request.state
            cache_hit = getattr(state, "cache_hit", None)
            tokens_input = getattr(state, "tokens_input", 0)
            tokens_output = getattr(state, "tokens_output", 0)

            app = request.app
            await app.state.metrics.record(
                elapsed,
                error=status >= 400,
                cache_hit=cache_hit,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
            )
            await log_request(
                app.state.pool,
                path=request.url.path,
                query=request.query_params.get("q"),
                status_code=status,
                latency_ms=round(elapsed, 2),
                # The column is NOT NULL: "never looked" and "looked and
                # missed" are both false as far as the history is concerned.
                cache_hit=bool(cache_hit),
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                error=None if status < 400 else f"HTTP {status}",
            )
