"use client";

import { useEffect, useState } from "react";
import { Chunk, createChunk, listChunks } from "./api-client";

export default function Home() {
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function refresh() {
    try {
      setChunks(await listChunks());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not reach the API");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSaving(true);
    try {
      await createChunk(text.trim(), source.trim());
      setText("");
      setSource("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save the chunk");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold">RAG at Scale</h1>
      <p className="mt-1 text-sm text-neutral-500">
        Add a chunk of text. Retrieval arrives once the corpus is ingested.
      </p>

      <form onSubmit={onSubmit} className="mt-8 space-y-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Chunk text"
          rows={4}
          className="w-full rounded-md border border-neutral-300 p-3 text-sm outline-none focus:border-neutral-500"
        />
        <input
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="Source (optional)"
          className="w-full rounded-md border border-neutral-300 p-3 text-sm outline-none focus:border-neutral-500"
        />
        <button
          type="submit"
          disabled={saving || !text.trim()}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {saving ? "Adding…" : "Add chunk"}
        </button>
      </form>

      {error && (
        <p className="mt-6 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}

      <section className="mt-10">
        <h2 className="text-sm font-medium text-neutral-500">
          Stored chunks ({chunks.length})
        </h2>
        <ul className="mt-3 space-y-3">
          {chunks.map((chunk) => (
            <li key={chunk.id} className="rounded-md border border-neutral-200 p-3">
              <p className="text-sm">{chunk.text}</p>
              {chunk.source && (
                <p className="mt-2 text-xs text-neutral-500">{chunk.source}</p>
              )}
            </li>
          ))}
        </ul>
        {chunks.length === 0 && !error && (
          <p className="mt-3 text-sm text-neutral-500">Nothing stored yet.</p>
        )}
      </section>
    </main>
  );
}
