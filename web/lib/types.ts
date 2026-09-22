/**
 * The contract between the frontend and the API.
 *
 * Everything here is live: documents, the PDFs behind them, search, answers
 * and metrics. Nothing on this page is generated locally.
 */

export type Role = "user" | "assistant";

/** Where a retrieved passage lives, precise enough to open the PDF at it. */
export type Citation = {
  /** 1-based marker used in the answer text, e.g. [1]. */
  index: number;
  chunkId: number;
  docId: string;
  docTitle: string | null;
  page: number;
  /** The passage itself. The viewer highlights this text on the page. */
  quote: string;
  /** Similarity, 1 is identical and 0 unrelated. */
  score: number;
};

export type MessageMetrics = {
  latencyMs: number;
  promptTokens: number;
  completionTokens: number;
  /** A cached answer costs no tokens, which is why the two are shown together. */
  cacheHit: boolean;
  retrievedChunks: number;
  model: string;
};

export type Message = {
  id: string;
  role: Role;
  content: string;
  createdAt: string;
  citations?: Citation[];
  metrics?: MessageMetrics;
  error?: string;
};

export type Conversation = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: Message[];
};

/** GET /documents */
export type DocumentSummary = {
  doc_id: string;
  title: string | null;
  collection: string | null;
  document_type: string | null;
  source_url: string | null;
  page_count: number | null;
  chunk_count: number | null;
};

/** GET /documents/{id} */
export type DocumentDetail = DocumentSummary & {
  source_organization: string | null;
  celex_number: string | null;
  publication_date: string | null;
  has_file: boolean;
};

/** GET /search */
export type SearchHit = {
  chunk_id: number;
  doc_id: string;
  title: string | null;
  text: string;
  page_start: number;
  page_end: number;
  score: number;
};

/** Events emitted while an answer is produced. */
export type ChatEvent =
  | { type: "citations"; citations: Citation[] }
  | { type: "token"; text: string }
  | { type: "done"; metrics: MessageMetrics }
  | { type: "error"; message: string };

/** POST /chat */
export type ChatApiResponse = {
  response: string;
  citations: {
    n: number;
    chunk_id: number;
    doc_id: string;
    title: string | null;
    page_start: number;
    page_end: number;
    quote: string;
    score: number;
  }[];
  thread_id: string;
  model_used: string;
  cached: boolean;
  retrieved_chunks: number;
  tokens_input: number;
  tokens_output: number;
  processing_time: number;
  timestamp: string;
};

export type TimePoint = { t: string; value: number };

/**
 * GET /analytics
 *
 * Every field is measured. Panels the system cannot measure — answer quality
 * scores, reranker timings, ANN index parameters — were removed rather than
 * filled with plausible numbers.
 */
export type Analytics = {
  window_hours: number;
  totals: {
    requests: number;
    errors: number;
    error_rate: number;
    avg_latency_ms: number;
    p50_latency_ms: number;
    p95_latency_ms: number;
    p99_latency_ms: number;
    tokens_input: number;
    tokens_output: number;
    /** Real token counts at configured prices, so it is an estimate. */
    estimated_cost_usd: number;
    estimated_cost_per_request_usd: number;
  };
  series: {
    t: string;
    requests: number;
    p95_latency_ms: number;
    error_rate: number;
    cache_hit_rate: number;
  }[];
  stages: { stage: string; p50_ms: number; p95_ms: number }[];
  cache_layers: {
    layer: string;
    meaning: string;
    hit_rate: number;
    saved_calls: number;
    lookups: number;
  }[];
  corpus: {
    documents: number;
    chunks: number;
    embedded_chunks: number;
    pages: number;
    embedding_model: string;
    embedding_dim: number;
    llm_model: string;
    index: string;
    retrieve_k: number;
  };
  slowest: { query: string; latency_ms: number; at: string; cache_hit: boolean }[];
};
