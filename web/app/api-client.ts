const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Chunk = {
  id: number;
  text: string;
  source: string | null;
};

export async function listChunks(): Promise<Chunk[]> {
  const res = await fetch(`${API_URL}/chunks`, { cache: "no-store" });
  if (!res.ok) throw new Error(`listChunks failed: ${res.status}`);
  return res.json();
}

export async function createChunk(text: string, source?: string): Promise<Chunk> {
  const res = await fetch(`${API_URL}/chunks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, source: source || null }),
  });
  if (!res.ok) throw new Error(`createChunk failed: ${res.status}`);
  return res.json();
}
