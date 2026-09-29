-- Approximate nearest-neighbour index on the chunk embeddings.
--
-- Without it every question is compared with all ~1M vectors: 5.7 s typical,
-- 23 s in the slow cases. With it: ~12 ms at 99% recall@10 (ef_search = 160,
-- set per query by the API). Measured in benchmarks_hnsw/.
--
-- m and ef_construction are pgvector's defaults and are fixed at build time;
-- ef_search is a query-time setting and can change without a rebuild.
--
-- Bulk loading: this runs when the database is created, so on a fresh
-- database the index exists before the chunks are loaded and every insert
-- must update the graph, which is much slower than building it afterwards.
-- For a full reload, drop it, load, then rebuild with enough memory:
--   DROP INDEX chunks_embedding_hnsw;
--   (load the chunks)
--   SET maintenance_work_mem = '2GB';
--   SET max_parallel_maintenance_workers = 3;
--   CREATE INDEX ...   (as below; 42 min for 1.06M vectors on a laptop)
CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw ON chunks
    USING hnsw (embedding halfvec_cosine_ops)
    WITH (m = 16, ef_construction = 64);
