CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE chunks (
    id         BIGSERIAL PRIMARY KEY,
    text       TEXT        NOT NULL,
    source     TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

