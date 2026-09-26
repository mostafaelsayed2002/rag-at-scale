"""Logging and request metrics.

- Redis: live counters (totals, cache hits), shared by all workers.
- Postgres: one row per request, for history, trends and percentiles.

Monitoring never fails a request: errors are logged and ignored.
"""

import json
import logging
import time
from datetime import datetime, timezone

from fastapi import Request
from psycopg import Error as PsycopgError
from psycopg.types.json import Jsonb
from redis.asyncio import Redis
from redis.exceptions import RedisError
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

PREFIX = "rag:v1:metrics"


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


class Metrics:
    """Request counters in Redis, shared by all workers.

    Redis counts safely even when two workers update at the same time.
    """

    FIELDS = (
        "requests_total",
        "errors_total",
        "cache_hits",
        "cache_misses",
        "tokens_input",
        "tokens_output",
    )

    def __init__(self, client: Redis):
        self.client = client

    async def record(
        self,
        latency_ms: float,
        *,
        error: bool = False,
        cache_hit: bool
        | None = None,  # None = cache not used (e.g. /health), so it is left out of the hit rate.
        tokens_input: int = 0,
        tokens_output: int = 0,
    ) -> None:
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
                     tokens_input, tokens_output, error, stages)
                VALUES (%(path)s, %(query)s, %(status_code)s, %(latency_ms)s,
                        %(cache_hit)s, %(tokens_input)s, %(tokens_output)s,
                        %(error)s, %(stages)s)
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

    # Measuring the metrics endpoints with themselves makes the numbers report
    # on the act of reading them: refreshing the dashboard would raise the
    # request count and add itself to the slowest queries. Health checks are
    # skipped for the same reason, since Docker calls one every five seconds.
    SKIP = {"/metrics", "/analytics", "/health", "/docs", "/openapi.json"}

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
            # {"embedding": 41.2, "retrieval": 8.9, "generation": 31980.0} —
            # where the time went, so a slow answer says which part to fix.
            stages = getattr(state, "stages", None)

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
                # Chat sends its question in the body, which the middleware
                # cannot read without consuming the stream, so the endpoint
                # leaves it on the state instead.
                query=getattr(state, "query", None) or request.query_params.get("q"),
                status_code=status,
                latency_ms=round(elapsed, 2),
                # The column is NOT NULL: "never looked" and "looked and
                # missed" are both false as far as the history is concerned.
                cache_hit=bool(cache_hit),
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                error=None if status < 400 else f"HTTP {status}",
                stages=Jsonb(stages) if stages else None,
            )
