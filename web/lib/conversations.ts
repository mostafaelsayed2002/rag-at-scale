"use client";

import { useCallback, useEffect, useState } from "react";
import { newId } from "./format";
import type { Conversation } from "./types";

const STORAGE_KEY = "rag.conversations.v1";

/**
 * Drop citations that cannot be opened.
 *
 * Stored conversations may predate live retrieval, when citations pointed at
 * a mock corpus with ids like "gdpr" and no page number. Those documents do
 * not exist, so clicking one would fail. The answers are kept; only the dead
 * links go.
 */
function usable(conversation: Conversation): Conversation {
  return {
    ...conversation,
    messages: conversation.messages.map((message) => {
      const citations = (message.citations ?? []).filter(
        (c) => typeof c?.docId === "string" && typeof c?.page === "number",
      );
      return citations.length ? { ...message, citations } : { ...message, citations: undefined };
    }),
  };
}

function load(): Conversation[] {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) return (JSON.parse(raw) as Conversation[]).map(usable);
  } catch {
    // Storage blocked or corrupted: start with an empty history.
  }
  return [];
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
