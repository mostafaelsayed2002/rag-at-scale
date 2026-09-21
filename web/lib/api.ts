import { MOCK_DOCUMENTS } from "./mock/documents";
import { mockChatStream } from "./mock/chat";
import { MOCK_METRICS } from "./mock/metrics";
import type { ChatEvent, DocumentContent, DocumentMeta, Message, SystemMetrics } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * Mocks are on unless explicitly disabled. Set NEXT_PUBLIC_USE_MOCKS=false at
 * build time once the backend implements the endpoints below.
 */
export const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS !== "false";

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path} failed with ${res.status}`);
  return res.json();
}

/** GET /documents */
export async function listDocuments(): Promise<DocumentMeta[]> {
  if (USE_MOCKS) {
    await delay(150);
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    return MOCK_DOCUMENTS.map(({ sections, ...meta }) => meta);
  }
  return getJson("/documents");
}

/** GET /documents/:id */
export async function getDocument(id: string): Promise<DocumentContent> {
  if (USE_MOCKS) {
    await delay(120);
    const doc = MOCK_DOCUMENTS.find((d) => d.id === id);
    if (!doc) throw new Error(`Document ${id} not found`);
    return doc;
  }
  return getJson(`/documents/${encodeURIComponent(id)}`);
}

/** GET /metrics */
export async function getMetrics(): Promise<SystemMetrics> {
  if (USE_MOCKS) {
    await delay(200);
    return MOCK_METRICS;
  }
  return getJson("/metrics");
}

/**
 * POST /chat, answered as server-sent events. Each event's data line is one
 * JSON-encoded ChatEvent.
 */
export async function* streamChat(
  query: string,
  history: Pick<Message, "role" | "content">[],
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  if (USE_MOCKS) {
    yield* mockChatStream(query, signal);
    return;
  }

  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({ query, history }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`Chat failed with ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trim())
        .join("");
      if (data) yield JSON.parse(data) as ChatEvent;
    }
  }
}
