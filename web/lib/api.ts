import type {
  Analytics,
  ChatApiResponse,
  ChatEvent,
  Citation,
  DocumentDetail,
  DocumentSummary,
  Message,
  SearchHit,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** The API's own message when it sends one, which is friendlier than a status code. */
async function detail(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return typeof body?.detail === "string" ? body.detail : fallback;
  } catch {
    return fallback;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await detail(res, `${path} failed with ${res.status}`));
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

/** The API's citation shape, mapped to the one the viewer works in. */
function toCitation(c: ChatApiResponse["citations"][number]): Citation {
  return {
    index: c.n,
    chunkId: c.chunk_id,
    docId: c.doc_id,
    docTitle: c.title,
    // A passage can span a page break; the viewer opens where it starts.
    page: c.page_start,
    quote: c.quote,
    score: c.score,
  };
}

/**
 * POST /chat.
 *
 * The answer arrives whole rather than token by token, so this yields it in
 * one piece. The generator shape is kept because the caller is written around
 * it, and because streaming is the next step rather than a rewrite.
 */
export async function* streamChat(
  query: string,
  _history: Pick<Message, "role" | "content">[],
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const started = performance.now();

  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query }),
    signal,
  });

  if (!res.ok) {
    // 429 is the quota running out, which is ordinary here and worth saying
    // plainly rather than reporting as a failure of the app.
    yield {
      type: "error",
      message: await detail(res, "The answer could not be generated. Please try again."),
    };
    return;
  }

  const body: ChatApiResponse = await res.json();
  if (signal?.aborted) return;

  if (body.citations.length) {
    yield { type: "citations", citations: body.citations.map(toCitation) };
  }
  yield { type: "token", text: body.response };
  yield {
    type: "done",
    metrics: {
      // Measured in the browser, so it includes the network, which is what
      // the person waiting actually experienced.
      latencyMs: Math.round(performance.now() - started),
      promptTokens: body.tokens_input,
      completionTokens: body.tokens_output,
      cacheHit: body.cached,
      retrievedChunks: body.retrieved_chunks,
      model: body.model_used,
    },
  };
}

/** GET /analytics */
export function getAnalytics(hours = 24): Promise<Analytics> {
  return getJson(`/analytics?hours=${hours}`);
}
