import type { SystemMetrics, TimePoint } from "../types";

// Seeded so the dashboard renders the same numbers on every load and on the
// server, which avoids hydration mismatches and flickering charts.
function seeded(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function series(points: number, base: number, spread: number, seed: number, daily = 0): TimePoint[] {
  const rand = seeded(seed);
  const end = Date.UTC(2026, 8, 15, 12);
  return Array.from({ length: points }, (_, i) => {
    const hour = (i + 12) % 24;
    // Business-hours bump, so traffic-shaped series look like traffic.
    const wave = daily * Math.max(0, Math.sin(((hour - 6) / 24) * Math.PI * 2));
    return {
      t: new Date(end - (points - 1 - i) * 3600_000).toISOString(),
      value: Math.max(0, base + wave + (rand() - 0.5) * spread),
    };
  });
}

export const MOCK_METRICS: SystemMetrics = {
  window: "Last 24 hours",
  generatedAt: "2026-09-15T12:00:00Z",
  totals: {
    queries: 18432,
    errorRate: 0.0042,
    cacheHitRate: 0.386,
    p50LatencyMs: 842,
    p95LatencyMs: 2140,
    p99LatencyMs: 3480,
    avgPromptTokens: 1712,
    avgCompletionTokens: 284,
    costPerQueryUsd: 0.00031,
    totalCostUsd: 5.71,
  },
  cacheLayers: [
    { layer: "Embedding cache", hitRate: 0.52, savedCalls: 9585 },
    { layer: "Semantic cache", hitRate: 0.21, savedCalls: 3871 },
    { layer: "Response cache", hitRate: 0.14, savedCalls: 2580 },
  ],
  latencyBreakdown: [
    { stage: "Query embedding", p50Ms: 9, p95Ms: 21 },
    { stage: "BM25 search", p50Ms: 18, p95Ms: 46 },
    { stage: "Vector search (HNSW)", p50Ms: 24, p95Ms: 61 },
    { stage: "RRF fusion", p50Ms: 2, p95Ms: 4 },
    { stage: "Cross-encoder rerank", p50Ms: 162, p95Ms: 318 },
    { stage: "LLM generation", p50Ms: 610, p95Ms: 1690 },
  ],
  quality: [
    { metric: "Faithfulness", value: 0.91, target: 0.85 },
    { metric: "Answer relevancy", value: 0.88, target: 0.85 },
    { metric: "Context precision", value: 0.83, target: 0.8 },
    { metric: "Context recall", value: 0.79, target: 0.8 },
  ],
  retrieval: {
    indexType: "HNSW (m=16, ef_construction=64)",
    efSearch: 80,
    recallAt10: 0.972,
    avgChunksRetrieved: 50,
    avgChunksAfterRerank: 5,
    corpusChunks: 312480,
  },
  series: {
    p95LatencyMs: series(24, 1900, 520, 7, 450),
    queries: series(24, 420, 110, 11, 780),
    cacheHitRate: series(24, 0.38, 0.08, 23, 0.04),
    errorRate: series(24, 0.004, 0.004, 31),
  },
};
