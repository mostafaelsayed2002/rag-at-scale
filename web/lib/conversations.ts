"use client";

import { useCallback, useEffect, useState } from "react";
import { buildCitations, buildMetrics, pickScript } from "./mock/chat";
import { newId } from "./format";
import type { Conversation, Message } from "./types";

const STORAGE_KEY = "rag.conversations.v1";

function seedConversation(title: string, questions: string[], hoursAgo: number): Conversation {
  const base = Date.now() - hoursAgo * 3600_000;
  const messages: Message[] = questions.flatMap((q, i) => {
    const script = pickScript(q);
    const at = new Date(base + i * 90_000).toISOString();
    return [
      { id: newId(), role: "user", content: q, createdAt: at },
      {
        id: newId(),
        role: "assistant",
        content: script.answer,
        createdAt: at,
        citations: buildCitations(script.sources),
        metrics: buildMetrics(q, script.answer),
      },
    ];
  });
  const at = new Date(base).toISOString();
  return { id: newId(), title, createdAt: at, updatedAt: at, messages };
}

/** Example history so a first visit does not open onto an empty sidebar. */
function seedConversations(): Conversation[] {
  return [
    seedConversation("Breach notification deadlines", ["How quickly must we report a data breach?"], 2),
    seedConversation(
      "Is CV screening high-risk?",
      ["Is our CV screening tool regulated under the AI Act?", "What are the maximum fines if we get it wrong?"],
      27,
    ),
    seedConversation("NIS2 incident reporting", ["What are the NIS2 incident reporting deadlines?"], 80),
    seedConversation("AI Act timeline", ["When does the AI Act apply?"], 24 * 12),
  ];
}

function load(): Conversation[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as Conversation[];
  } catch {
    // Storage blocked or corrupted: fall through to the seed data.
  }
  return seedConversations();
}

function save(conversations: Conversation[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(conversations));
  } catch {
    // Private mode or quota exceeded: history just won't survive a reload.
  }
}

export function titleFromQuery(query: string): string {
  const clean = query.replace(/\s+/g, " ").trim();
  return clean.length > 48 ? `${clean.slice(0, 45).trimEnd()}…` : clean;
}

/**
 * Conversation history kept in the browser. Swapped for API calls once the
 * backend stores conversations; the returned interface stays the same.
 */
export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [hydrated, setHydrated] = useState(false);

  // Read storage after mount: the server has no localStorage, and reading it
  // during render would produce different HTML on the server and client.
  useEffect(() => {
    setConversations(load());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) save(conversations);
  }, [conversations, hydrated]);

  const create = useCallback((firstQuery: string): Conversation => {
    const now = new Date().toISOString();
    const conversation: Conversation = {
      id: newId(),
      title: titleFromQuery(firstQuery),
      createdAt: now,
      updatedAt: now,
      messages: [],
    };
    setConversations((list) => [conversation, ...list]);
    return conversation;
  }, []);

  const update = useCallback((id: string, change: (c: Conversation) => Conversation) => {
    setConversations((list) => list.map((c) => (c.id === id ? change(c) : c)));
  }, []);

  const rename = useCallback(
    (id: string, title: string) => update(id, (c) => ({ ...c, title: title.trim() || c.title })),
    [update],
  );

  const remove = useCallback((id: string) => {
    setConversations((list) => list.filter((c) => c.id !== id));
  }, []);

  return { conversations, hydrated, create, update, rename, remove };
}
