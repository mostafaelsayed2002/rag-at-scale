/**
 * The contract between the frontend and the API. Everything is mocked today;
 * the backend should return exactly these shapes so the mocks can be removed
 * without touching a component.
 */

export type Role = "user" | "assistant";

/** Where a retrieved passage lives, precise enough to open it at the right spot. */
export type Citation = {
  /** 1-based marker used in the answer text, e.g. [1]. */
  index: number;
  documentId: string;
  chunkId: string;
  /** Page for PDFs, null for markdown. */
  page: number | null;
  /** Anchor of the section inside the document, used to scroll and highlight. */
  sectionId: string;
  /** Human label for the location, e.g. "Article 33". */
  locator: string;
  snippet: string;
  /** Retrieval score after reranking, 0 to 1. */
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

export type DocumentFormat = "pdf" | "md";

export type DocumentMeta = {
  id: string;
  title: string;
  shortTitle: string;
  format: DocumentFormat;
  /** Corpus tier, e.g. "Legislation" or "EDPB". */
  collection: string;
  identifier: string;
  publishedAt: string;
  pageCount: number | null;
  chunkCount: number;
  sourceUrl: string;
};

export type DocumentSection = {
  id: string;
  heading: string;
  page: number | null;
  paragraphs: string[];
};

export type DocumentContent = DocumentMeta & {
  sections: DocumentSection[];
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
