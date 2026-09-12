"use client";

import { useState } from "react";
import { SearchHit, createChunk, search } from "./api-client";

export default function Home() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [text, setText] = useState("");
  const [source, setSource] = useState("");
  const [saving, setSaving] = useState(false);

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    try {
      setHits(await search(query.trim()));
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
    } finally {
      setSearching(false);
    }
  }

  async function onAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSaving(true);
    try {
      await createChunk(text.trim(), source.trim());
      setText("");
      setSource("");
      setError(null);
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
        Semantic search over arXiv abstracts.
      </p>

      <form onSubmit={onSearch} className="mt-8 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What are you looking for?"
          className="flex-1 rounded-md border border-neutral-300 p-3 text-sm outline-none focus:border-neutral-500"
        />
        <button
          type="submit"
          disabled={searching || !query.trim()}
          className="rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {searching ? "Searching…" : "Search"}
        </button>
      </form>

      {error && (
        <p className="mt-6 rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</p>
      )}

      {hits && (
        <section className="mt-8">
          <h2 className="text-sm font-medium text-neutral-500">
            {hits.length} result{hits.length === 1 ? "" : "s"}
          </h2>
          <ul className="mt-3 space-y-3">
            {hits.map((hit) => (
              <li key={hit.id} className="rounded-md border border-neutral-200 p-3">
                <div className="flex items-baseline justify-between gap-4">
                  <p className="text-sm font-medium">{hit.source ?? "Untitled"}</p>
                  <span className="shrink-0 text-xs tabular-nums text-neutral-400">
                    {hit.score.toFixed(3)}
                  </span>
                </div>
                <p className="mt-2 line-clamp-4 text-sm text-neutral-600">{hit.text}</p>
              </li>
            ))}
          </ul>
          {hits.length === 0 && (
            <p className="mt-3 text-sm text-neutral-500">Nothing matched.</p>
          )}
        </section>
      )}

      <details className="mt-12 border-t border-neutral-200 pt-6">
        <summary className="cursor-pointer text-sm text-neutral-500">
          Add a chunk manually
        </summary>
        <form onSubmit={onAdd} className="mt-4 space-y-3">
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
      </details>

      <footer className="mt-12 border-t border-neutral-200 pt-4 text-xs text-neutral-400">
        Deployed automatically from main.
      </footer>
    </main>
  );
}
