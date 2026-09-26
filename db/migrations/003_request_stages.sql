-- Where the time went inside a request: embedding, retrieval, generation.
--
-- A single latency number says an answer took 32 seconds without saying which
-- part to fix. JSONB rather than three columns: a cache hit has no stages.

ALTER TABLE request_log ADD COLUMN IF NOT EXISTS stages JSONB;
