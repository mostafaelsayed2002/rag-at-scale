CREATE EXTENSION IF NOT EXISTS vector;

-- One row per EU act in force. Chunks point here, so a title or its topics
-- are stored once rather than repeated on every chunk.
CREATE TABLE documents (
    doc_id              TEXT PRIMARY KEY,  -- the CELEX number, e.g. 32016R0679
    title               TEXT,
    source_url          TEXT,              -- the act on EUR-Lex
    source_organization TEXT,
    document_type       TEXT,              -- CELLAR resource type: REG, DIR, DEC_IMPL...
    celex_number        TEXT,
    collection          TEXT,              -- readable group: Regulation, Directive, Decision...
    publication_date    DATE,
    -- EUROVOC subjects, e.g. {data protection, personal data}. An act usually
    -- has several, which is why this is a list and filters use the GIN index.
    topics              TEXT[] NOT NULL DEFAULT '{}',
    -- Content hash. Loading skips a document whose hash is unchanged, which
    -- is what makes reruns cheap and safe to repeat.
    sha256              TEXT NOT NULL,
    page_count          INTEGER,
    chunk_count         INTEGER,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX documents_topics_idx ON documents USING GIN (topics);

CREATE TABLE chunks (
    id          BIGSERIAL PRIMARY KEY,
    doc_id      TEXT        NOT NULL REFERENCES documents (doc_id) ON DELETE CASCADE,
    chunk_index INTEGER     NOT NULL,  -- position within the document
    text        TEXT        NOT NULL,
    -- A chunk can cross a page break, so both ends are recorded; a citation
    -- needs the page the passage starts on.
    page_start  INTEGER     NOT NULL,
    page_end    INTEGER     NOT NULL,
    tokens      INTEGER     NOT NULL,  -- as the embedding model counts them
    -- bge-base-en-v1.5, 768 dimensions, in half precision: half the memory of
    -- VECTOR(768) for a negligible loss in recall, which is what lets a
    -- million chunks and their index fit on a small server.
    -- Must match EMBEDDING_DIM in ingest/config.py.
    embedding   HALFVEC(768),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, chunk_index)
);

-- Re-loading one document deletes its chunks first; this makes that fast.
CREATE INDEX chunks_doc_id_idx ON chunks (doc_id);

-- No vector index yet: HNSW is built deliberately after loading, so build
-- time, memory and the recall/latency trade-off can be measured (and a
-- million inserts are much faster without an index to maintain).
