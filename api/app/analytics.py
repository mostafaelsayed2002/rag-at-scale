"""The dashboard's numbers, computed from what actually happened.

Everything here comes from request_log or from the corpus tables. Nothing is
estimated and nothing is invented: a panel with no data behind it should be
removed from the dashboard rather than filled with a plausible number.
"""

import logging

from .config import settings

logger = logging.getLogger(__name__)

# Percentiles are the point of keeping the rows: an average hides the slow
# requests, and the slow ones are what users notice.
TOTALS_SQL = """
    SELECT count(*)                                          AS requests,
           coalesce(avg(latency_ms), 0)                      AS avg_latency_ms,
           coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms), 0) AS p50_latency_ms,
           coalesce(percentile_cont(0.9) WITHIN GROUP (ORDER BY latency_ms), 0) AS p90_latency_ms,
           coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0) AS p95_latency_ms,
           coalesce(percentile_cont(0.99) WITHIN GROUP (ORDER BY latency_ms), 0) AS p99_latency_ms,
           -- The slowest request itself. Below a few hundred rows the high
           -- percentiles are all pointing at it, and showing it says so.
           coalesce(max(latency_ms), 0)                       AS max_latency_ms,
           coalesce(min(latency_ms), 0)                       AS min_latency_ms,
           count(*) FILTER (WHERE status_code >= 400)        AS errors,
           count(*) FILTER (WHERE cache_hit)                 AS cache_hits,
           coalesce(sum(tokens_input), 0)                    AS tokens_input,
           coalesce(sum(tokens_output), 0)                   AS tokens_output
    FROM request_log
    WHERE created_at >= now() - make_interval(hours => %s)
"""

# date_trunc gives one row per hour that had traffic; hours with none are
# filled in by the caller, so the chart shows a gap rather than skipping it.
SERIES_SQL = """
    SELECT date_trunc('hour', created_at)                    AS hour,
           count(*)                                          AS requests,
           coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0) AS p95_latency_ms,
           count(*) FILTER (WHERE status_code >= 400)::float / count(*)          AS error_rate,
           count(*) FILTER (WHERE cache_hit)::float / count(*)                   AS cache_hit_rate
    FROM request_log
    WHERE created_at >= now() - make_interval(hours => %s)
    GROUP BY hour
    ORDER BY hour
"""

# Stage timings live in JSONB: a cache hit has no stages at all.
STAGES_SQL = """
    SELECT key                                                        AS stage,
           count(*)                                                   AS samples,
           coalesce(percentile_cont(0.5) WITHIN GROUP (ORDER BY ms), 0)  AS p50_ms,
           coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY ms), 0) AS p95_ms
    FROM request_log,
         LATERAL jsonb_each_text(stages) AS entry(key, value),
         LATERAL (SELECT value::float AS ms) AS parsed
    WHERE stages IS NOT NULL
      AND created_at >= now() - make_interval(hours => %s)
    GROUP BY key
    ORDER BY p50_ms DESC
"""

CORPUS_SQL = """
    SELECT (SELECT count(*) FROM documents)                          AS documents,
           (SELECT count(*) FROM chunks)                             AS chunks,
           (SELECT count(*) FROM chunks WHERE embedding IS NOT NULL) AS embedded_chunks,
           (SELECT coalesce(sum(page_count), 0) FROM documents)      AS pages
"""

SLOWEST_SQL = """
    SELECT query, round(latency_ms) AS latency_ms, created_at, cache_hit
    FROM request_log
    WHERE created_at >= now() - make_interval(hours => %s)
    ORDER BY latency_ms DESC
    LIMIT 5
"""


def estimated_cost(tokens_input: int, tokens_output: int) -> float:
    """Cost at the configured rates. Labelled an estimate wherever it is shown.

    The token counts are real, reported by the API. The prices are settings,
    because a published price is not something the code can measure.
    """
    return (
        tokens_input / 1_000_000 * settings.usd_per_million_input_tokens
        + tokens_output / 1_000_000 * settings.usd_per_million_output_tokens
    )


CACHE_SQL = """
    SELECT count(*) FILTER (WHERE cache_hit) AS hits,
           count(*)                          AS lookups
    FROM request_log
    WHERE created_at >= now() - make_interval(hours => %s)
"""


async def overview(pool, hours: int = 24) -> dict:
    """Everything the analytics page shows, in one round of queries."""
    async with pool.connection() as conn:
        totals = await (await conn.execute(TOTALS_SQL, (hours,))).fetchone()
        series = await (await conn.execute(SERIES_SQL, (hours,))).fetchall()
        stages = await (await conn.execute(STAGES_SQL, (hours,))).fetchall()
        corpus = await (await conn.execute(CORPUS_SQL)).fetchone()
        slowest = await (await conn.execute(SLOWEST_SQL, (hours,))).fetchall()
        cache = await (await conn.execute(CACHE_SQL, (hours,))).fetchone()

    requests = totals["requests"]
    tokens_input = int(totals["tokens_input"])
    tokens_output = int(totals["tokens_output"])
    cost = estimated_cost(tokens_input, tokens_output)

    return {
        "window_hours": hours,
        "totals": {
            "requests": requests,
            "errors": totals["errors"],
            "error_rate": round(totals["errors"] / requests, 4) if requests else 0.0,
            "avg_latency_ms": round(float(totals["avg_latency_ms"]), 1),
            "p50_latency_ms": round(float(totals["p50_latency_ms"]), 1),
            "p90_latency_ms": round(float(totals["p90_latency_ms"]), 1),
            "p95_latency_ms": round(float(totals["p95_latency_ms"]), 1),
            "p99_latency_ms": round(float(totals["p99_latency_ms"]), 1),
            "max_latency_ms": round(float(totals["max_latency_ms"]), 1),
            "min_latency_ms": round(float(totals["min_latency_ms"]), 1),
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "estimated_cost_usd": round(cost, 6),
            "estimated_cost_per_request_usd": round(cost / requests, 6) if requests else 0.0,
        },
        "series": [
            {
                "t": row["hour"].isoformat(),
                "requests": row["requests"],
                "p95_latency_ms": round(float(row["p95_latency_ms"]), 1),
                "error_rate": round(float(row["error_rate"]), 4),
                "cache_hit_rate": round(float(row["cache_hit_rate"]), 4),
            }
            for row in series
        ],
        "stages": [
            {
                "stage": row["stage"],
                # Carried so the dashboard can tell one measurement from a
                # distribution: with few rows every percentile is the same.
                "samples": row["samples"],
                "p50_ms": round(float(row["p50_ms"]), 1),
                "p95_ms": round(float(row["p95_ms"]), 1),
            }
            for row in stages
        ],
        # Counted from the history, so it covers the same window as the rest.
        "cache": {
            "hits": cache["hits"],
            "lookups": cache["lookups"],
            "hit_rate": round(cache["hits"] / cache["lookups"], 4) if cache["lookups"] else 0.0,
        },
        "corpus": {
            "documents": corpus["documents"],
            "chunks": corpus["chunks"],
            "embedded_chunks": corpus["embedded_chunks"],
            "pages": int(corpus["pages"]),
            "embedding_model": settings.embedding_model,
            "embedding_dim": settings.embedding_dim,
            "llm_model": settings.llm_model,
            # Honest about what the search actually is: there is no ANN index
            # on the table, so every query scans every embedded chunk. At this
            # corpus size that is fast, and claiming HNSW would be a lie.
            "index": "exact scan (no ANN index)",
            "retrieve_k": settings.retrieve_k,
        },
        "slowest": [
            {
                "query": row["query"],
                "latency_ms": float(row["latency_ms"]),
                "at": row["created_at"].isoformat(),
                "cache_hit": row["cache_hit"],
            }
            for row in slowest
        ],
    }
