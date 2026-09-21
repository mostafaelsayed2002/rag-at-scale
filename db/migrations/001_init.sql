CREATE EXTENSION IF NOT EXISTS vector;

-- One row per PDF in the corpus. Chunks point here, so a title or a source
-- URL is stored once rather than repeated on every chunk.
CREATE TABLE documents (
    doc_id              TEXT PRIMARY KEY,  -- the file name without .pdf
    title               TEXT,
    source_url          TEXT,
    source_organization TEXT,
    document_type       TEXT,
    celex_number        TEXT,
    collection          TEXT,              -- top folder: legislation, edpb, curia...
    publication_date    DATE,
    -- Content hash. Ingestion skips a document whose hash is unchanged, which
    -- is what makes reruns cheap and safe to repeat.
    sha256              TEXT NOT NULL,
    page_count          INTEGER,
    chunk_count         INTEGER,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chunks (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      TEXT        NOT NULL REFERENCES documents (doc_id) ON DELETE CASCADE,
    chunk_index INTEGER     NOT NULL,  -- position within the document
    text        TEXT        NOT NULL,
    -- A chunk can cross a page break, so both ends are recorded; a citation
    -- needs the page the passage starts on.
    page_start  INTEGER     NOT NULL,
    page_end    INTEGER     NOT NULL,
    -- 768 dimensions: gemini-embedding-2 at its smallest recommended size.
    -- Must match EMBEDDING_DIM in ingest/config.py.
    embedding   VECTOR(768),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, chunk_index)
);

-- Re-ingesting one document deletes its chunks first; this makes that fast.
CREATE INDEX chunks_doc_id_idx ON chunks (doc_id);

-- No vector index yet. Exact search over a few thousand rows is fast, and
-- week 2 builds HNSW deliberately so build time, memory and the
-- recall/latency trade-off can be measured.
