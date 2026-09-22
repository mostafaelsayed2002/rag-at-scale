import { pickScript } from "./mock/chat";
import { MOCK_METRICS } from "./mock/metrics";
import type {
  ChatEvent,
  DocumentDetail,
  DocumentSummary,
  Message,
  SearchHit,
  SystemMetrics,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} failed with ${res.status}`);
  return res.json();
}

/** GET /documents */
export function listDocuments(): Promise<DocumentSummary[]> {
  return getJson("/documents");
}

/** GET /documents/{id} */
export function getDocument(docId: string): Promise<DocumentDetail> {
  return getJson(`/documents/${encodeURIComponent(docId)}`);
}

/** The PDF itself. Given straight to the viewer, which fetches it by range. */
export function documentFileUrl(docId: string): string {
  return `${API_URL}/documents/${encodeURIComponent(docId)}/file`;
}

/** GET /search */
export function search(q: string, k = 8): Promise<SearchHit[]> {
  const params = new URLSearchParams({ q, k: String(k) });
  return getJson(`/search?${params}`);
}

/**
 * Stands in for POST /chat.
 *
 * Answers are scripted, but their citations come from chunks that are really
 * in the database, so clicking one opens the actual PDF at the actual page
 * and highlights the passage. No embedding call is made, which keeps the
 * demo working when the API quota is spent.
 */
export async function* streamChat(
  query: string,
  _history: Pick<Message, "role" | "content">[],
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const started = performance.now();
  const script = pickScript(query);

  // Retrieval would happen before generation, so the citations arrive first.
  await delay(500);
  if (signal?.aborted) return;
  if (script.citations.length) yield { type: "citations", citations: script.citations };

  for (const piece of script.answer.match(/\S+\s*/g) ?? []) {
    if (signal?.aborted) return;
    await delay(14 + Math.random() * 22);
    yield { type: "token", text: piece };
  }

  yield {
    type: "done",
    metrics: {
      latencyMs: Math.round(performance.now() - started),
      promptTokens: 0,
      completionTokens: 0,
      cacheHit: "none",
      retrievedChunks: script.citations.length,
    },
  };
}

/** GET /metrics, still mocked. */
export async function getMetrics(): Promise<SystemMetrics> {
  await delay(200);
  return MOCK_METRICS;
}
