"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { BarChart3, Check, ChevronRight, MessageSquare, PanelLeft, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { BUCKET_ORDER, dateBucket } from "@/lib/format";
import type { Conversation } from "@/lib/types";
import { IconButton } from "../ui";

type Props = {
  conversations: Conversation[];
  hydrated: boolean;
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
};

export function Sidebar({ conversations, hydrated, activeId, onSelect, onNew, onRename, onDelete, onClose }: Props) {
  const [filter, setFilter] = useState("");

  const groups = useMemo(() => {
    const q = filter.trim().toLowerCase();
    const visible = [...conversations]
      .filter((c) => !q || c.title.toLowerCase().includes(q))
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
    const byBucket = new Map<string, Conversation[]>();
    for (const c of visible) {
      const bucket = dateBucket(c.updatedAt);
      byBucket.set(bucket, [...(byBucket.get(bucket) ?? []), c]);
    }
    return BUCKET_ORDER.filter((b) => byBucket.has(b)).map((b) => ({ label: b, items: byBucket.get(b)! }));
  }, [conversations, filter]);

  return (
    <nav aria-label="Conversation history" className="flex h-full w-72 flex-col bg-panel">
      <div className="flex h-14 items-center justify-between px-3">
        <Link href="/" className="flex items-center gap-2 rounded-md px-1.5 py-1 text-sm font-semibold tracking-tight">
          <span className="grid h-6 w-6 place-items-center rounded-md bg-accent text-[11px] font-bold text-accent-fg">R</span>
          RAG at Scale
        </Link>
        <IconButton label="Close sidebar" onClick={onClose}>
          <PanelLeft size={18} />
        </IconButton>
      </div>

      <div className="space-y-2 px-3 pb-2">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-lg border border-line bg-elevated px-3 py-2 text-sm font-medium shadow-sm transition-colors hover:bg-fg/[0.03] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
        >
          <Plus size={16} />
          New chat
        </button>
        <label className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm text-muted focus-within:bg-fg/[0.04]">
          <Search size={15} aria-hidden />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Search chats"
            aria-label="Search chats"
            className="w-full bg-transparent text-fg outline-none placeholder:text-subtle"
          />
        </label>
      </div>

      <div className="scrollbar-thin flex-1 overflow-y-auto px-2 pb-4">
        {!hydrated ? (
          <div className="space-y-2 px-2 pt-3">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-7 animate-pulse rounded-md bg-fg/[0.05]" />
            ))}
          </div>
        ) : groups.length === 0 ? (
          <p className="px-3 pt-6 text-center text-sm text-subtle">{filter ? "No chats match." : "No chats yet."}</p>
        ) : (
          groups.map((group) => (
            <section key={group.label} className="pt-3">
              <h2 className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-subtle">{group.label}</h2>
              <ul>
                {group.items.map((c) => (
                  <ConversationItem
                    key={c.id}
                    conversation={c}
                    active={c.id === activeId}
                    onSelect={() => onSelect(c.id)}
                    onRename={(title) => onRename(c.id, title)}
                    onDelete={() => onDelete(c.id)}
                  />
                ))}
              </ul>
            </section>
          ))
        )}
      </div>

      <div className="border-t border-line p-2">
        <Link
          href="/analytics"
          className="group flex items-center gap-3 rounded-xl border border-line bg-elevated px-3 py-2.5 shadow-sm transition-colors hover:border-accent/40 hover:bg-accent-soft"
        >
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-accent-soft text-accent">
            <BarChart3 size={16} aria-hidden />
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex items-center gap-1.5 text-sm font-medium">
              Live system analytics
              <span className="h-1.5 w-1.5 rounded-full bg-good" aria-hidden />
            </span>
            <span className="block truncate text-xs text-muted">Latency, cache hits, cost</span>
          </span>
          <ChevronRight size={15} className="text-subtle transition-transform group-hover:translate-x-0.5" aria-hidden />
        </Link>
      </div>
    </nav>
  );
}

function ConversationItem({
  conversation,
  active,
  onSelect,
  onRename,
  onDelete,
}: {
  conversation: Conversation;
  active: boolean;
  onSelect: () => void;
  onRename: (title: string) => void;
  onDelete: () => void;
}) {
  const [mode, setMode] = useState<"idle" | "rename" | "confirm">("idle");
  const [draft, setDraft] = useState(conversation.title);

  if (mode === "rename") {
    return (
      <li>
        <form
          className="flex items-center gap-1 rounded-lg bg-fg/[0.07] px-1.5 py-1"
          onSubmit={(e) => {
            e.preventDefault();
            onRename(draft);
            setMode("idle");
          }}
        >
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && setMode("idle")}
            aria-label="Chat title"
            className="min-w-0 flex-1 rounded bg-elevated px-1.5 py-0.5 text-sm outline-none ring-1 ring-accent/50"
          />
          <IconButton label="Save title" type="submit" className="h-7 w-7">
            <Check size={14} />
          </IconButton>
        </form>
      </li>
    );
  }

  return (
    <li className="group relative">
      <button
        type="button"
        onClick={onSelect}
        aria-current={active ? "page" : undefined}
        className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 ${
          active ? "bg-fg/[0.08] text-fg" : "text-fg/80 hover:bg-fg/[0.05]"
        }`}
      >
        <MessageSquare size={14} className="shrink-0 text-subtle" aria-hidden />
        <span className="truncate pr-12">{conversation.title}</span>
      </button>

      {mode === "confirm" ? (
        <div className="absolute inset-y-0 right-1 flex items-center gap-0.5 rounded-md bg-panel pl-1">
          <button
            type="button"
            onClick={onDelete}
            className="rounded-md bg-bad px-2 py-0.5 text-xs font-medium text-white hover:opacity-90"
          >
            Delete
          </button>
          <IconButton label="Cancel" className="h-7 w-7" onClick={() => setMode("idle")}>
            <X size={14} />
          </IconButton>
        </div>
      ) : (
        <div
          className={`absolute inset-y-0 right-1 flex items-center gap-0.5 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100 ${
            active ? "opacity-100" : ""
          }`}
        >
          <IconButton
            label="Rename chat"
            className="h-7 w-7"
            onClick={() => {
              setDraft(conversation.title);
              setMode("rename");
            }}
          >
            <Pencil size={13} />
          </IconButton>
          <IconButton label="Delete chat" className="h-7 w-7 hover:text-bad" onClick={() => setMode("confirm")}>
            <Trash2 size={13} />
          </IconButton>
        </div>
      )}
    </li>
  );
}
