CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunks (
    id         BIGSERIAL PRIMARY KEY,
    text       TEXT        NOT NULL,
    source     TEXT,
    -- 384 dimensions, fixed by bge-small-en-v1.5. Postgres enforces the size,
    -- so a wrongly shaped vector is rejected at insert rather than stored.
    -- Nullable: a row can be inserted before it has been embedded.
    embedding  VECTOR(384),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- No index yet. Exact search over 10k rows is fast, and week 2 builds HNSW
-- deliberately so build time and the recall/latency tradeoff can be measured.
