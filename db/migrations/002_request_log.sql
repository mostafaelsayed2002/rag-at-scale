-- One row per chat request: the history behind the analytics page.
--
-- Redis holds the running counters, which answer "how are we doing now".
-- They cannot answer "what was the 95th percentile last Tuesday", because a
-- counter keeps a sum and throws the measurements away. This table keeps them.

CREATE TABLE IF NOT EXISTS request_log (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    query TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    latency_ms DOUBLE PRECISION NOT NULL,
    cache_hit BOOLEAN NOT NULL DEFAULT false,
    tokens_input INTEGER NOT NULL DEFAULT 0,
    tokens_output INTEGER NOT NULL DEFAULT 0,
    error TEXT
);

-- Every analytics query is "the recent ones", either a time window or the
-- latest N, so the index is on time, newest first.
CREATE INDEX IF NOT EXISTS request_log_created_at_idx ON request_log (created_at DESC);
