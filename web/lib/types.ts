/**
 * The contract between the frontend and the API.
 *
 * Documents, the PDFs behind them and search are live. Chat generation is
 * still mocked: an answer is composed locally from real retrieved passages
 * until POST /chat exists.
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
  cacheHit: "none" | "embedding" | "semantic" | "response";
  retrievedChunks: number;
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

/** Events emitted while an answer is generated. */
export type ChatEvent =
  | { type: "citations"; citations: Citation[] }
  | { type: "token"; text: string }
  | { type: "done"; metrics: MessageMetrics }
  | { type: "error"; message: string };

export type TimePoint = { t: string; value: number };

export type SystemMetrics = {
  window: string;
  generatedAt: string;
  totals: {
    queries: number;
    errorRate: number;
    cacheHitRate: number;
    p50LatencyMs: number;
    p95LatencyMs: number;
    p99LatencyMs: number;
    avgPromptTokens: number;
    avgCompletionTokens: number;
    costPerQueryUsd: number;
    totalCostUsd: number;
  };
  cacheLayers: { layer: string; hitRate: number; savedCalls: number }[];
  latencyBreakdown: { stage: string; p50Ms: number; p95Ms: number }[];
  quality: { metric: string; value: number; target: number }[];
  retrieval: {
    indexType: string;
    efSearch: number;
    recallAt10: number;
    avgChunksRetrieved: number;
    avgChunksAfterRerank: number;
    corpusChunks: number;
  };
  series: {
    p95LatencyMs: TimePoint[];
    queries: TimePoint[];
    cacheHitRate: TimePoint[];
    errorRate: TimePoint[];
  };
};
