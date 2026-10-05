import type {
  Analytics,
  ChatApiResponse,
  ChatEvent,
  Citation,
  DocumentDetail,
  DocumentPage,
  Message,
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

/** GET /documents: one page of acts. The whole corpus is ~19 MB, so it is
 * searched and paged by the API rather than downloaded. */
export function listDocuments(params: {
  q?: string;
  collection?: string;
  limit?: number;
  offset?: number;
}): Promise<DocumentPage> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.collection) search.set("collection", params.collection);
  search.set("limit", String(params.limit ?? 50));
  search.set("offset", String(params.offset ?? 0));
  return getJson(`/documents?${search}`);
}

/** GET /documents/{id} */
export function getDocument(docId: string): Promise<DocumentDetail> {
  return getJson(`/documents/${encodeURIComponent(docId)}`);
}

/** The PDF itself. Given straight to the viewer, which fetches it by range. */
export function documentFileUrl(docId: string): string {
  return `${API_URL}/documents/${encodeURIComponent(docId)}/file`;
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
 * Server-Sent Events from a fetch response: yields each event's name and data.
 * EventSource would parse them itself, but it can only send GET, and the
 * question goes in a POST body.
 */
async function* readEvents(res: Response): AsyncGenerator<{ event: string; data: string }> {
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) return;
    buffer += value;
    // An event ends with a blank line; the last piece may still be arriving.
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      let event = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data += line.slice(6);
      }
      yield { event, data };
    }
  }
}

/**
 * POST /chat/stream: the answer as it is written, then its citations and costs.
 */
export async function* streamChat(
  query: string,
  _history: Pick<Message, "role" | "content">[],
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const started = performance.now();

  const res = await fetch(`${API_URL}/chat/stream`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query }),
    signal,
  });

  if (!res.ok) {
    // 429 here is the rate limit, which is ordinary and worth saying plainly
    // rather than reporting as a failure of the app.
    yield {
      type: "error",
      message: await detail(res, "The answer could not be generated. Please try again."),
    };
    return;
  }

  for await (const { event, data } of readEvents(res)) {
    if (signal?.aborted) return;
    if (event === "token") {
      yield { type: "token", text: JSON.parse(data).text };
    } else if (event === "error") {
      yield { type: "error", message: JSON.parse(data).message };
    } else if (event === "done") {
      const body: ChatApiResponse = JSON.parse(data);
      if (body.citations.length) {
        yield { type: "citations", citations: body.citations.map(toCitation) };
      }
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
  }
}

/** GET /analytics */
export function getAnalytics(hours = 24): Promise<Analytics> {
  return getJson(`/analytics?hours=${hours}`);
}
