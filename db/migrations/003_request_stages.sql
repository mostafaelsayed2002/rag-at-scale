-- Where the time went inside a request: embedding, retrieval, generation.
--
-- A single latency number says an answer took 32 seconds without saying which
-- part to fix. JSONB rather than three columns because the stages differ by
-- endpoint, and a search has no generation step.

ALTER TABLE request_log ADD COLUMN IF NOT EXISTS stages JSONB;
