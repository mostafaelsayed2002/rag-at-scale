"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { BarChart3, Library, PanelLeft, SquarePen } from "lucide-react";
import { streamChat } from "@/lib/api";
import { useConversations } from "@/lib/conversations";
import { newId } from "@/lib/format";
import { useMediaQuery } from "@/lib/use-media-query";
import type { Citation, Message } from "@/lib/types";
import { DemoBadge, IconButton } from "../ui";
import { DocumentsPanel, type DocumentTarget } from "../documents/DocumentsPanel";
import { Composer } from "./Composer";
import { EmptyState } from "./EmptyState";
import { AssistantMessage, UserMessage } from "./Message";
import { Sidebar } from "./Sidebar";

/** The answer being generated, kept outside history so each token doesn't rewrite storage. */
type Draft = { conversationId: string; message: Message };

export function ChatApp() {
  const { conversations, hydrated, create, update, rename, remove } = useConversations();
  const [activeId, setActiveId] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Sidebars sit beside the chat on wide screens and overlay it on narrow ones.
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const isWide = useMediaQuery("(min-width: 1280px)");
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);
  const [docTarget, setDocTarget] = useState<DocumentTarget | null>(null);

  useEffect(() => setLeftOpen(isDesktop), [isDesktop]);

  const active = conversations.find((c) => c.id === activeId) ?? null;
  const streaming = draft !== null;

  const messages: Message[] = active
    ? active.messages.map((m) => (draft && draft.message.id === m.id ? draft.message : m))
    : [];

  const closeOverlays = useCallback(() => {
    if (!isDesktop) setLeftOpen(false);
  }, [isDesktop]);

  const openCitation = useCallback(
    (citation: Citation) => {
      setDocTarget({ documentId: citation.documentId, sectionId: citation.sectionId, nonce: Date.now() });
      setRightOpen(true);
      if (!isDesktop) setLeftOpen(false);
    },
    [isDesktop],
  );

  const send = useCallback(
    async (text: string) => {
      if (streaming) return;

      const conversation = active ?? create(text);
      if (!active) setActiveId(conversation.id);

      const history = conversation.messages.map(({ role, content }) => ({ role, content }));
      const now = new Date().toISOString();
      const userMessage: Message = { id: newId(), role: "user", content: text, createdAt: now };
      const assistant: Message = { id: newId(), role: "assistant", content: "", createdAt: now };

      update(conversation.id, (c) => ({ ...c, updatedAt: now, messages: [...c.messages, userMessage, assistant] }));

      const controller = new AbortController();
      abortRef.current = controller;
      let current = assistant;
      setDraft({ conversationId: conversation.id, message: current });

      try {
        for await (const event of streamChat(text, history, controller.signal)) {
          if (event.type === "citations") current = { ...current, citations: event.citations };
          else if (event.type === "token") current = { ...current, content: current.content + event.text };
          else if (event.type === "done") current = { ...current, metrics: event.metrics };
          else if (event.type === "error") current = { ...current, error: event.message };
          setDraft({ conversationId: conversation.id, message: current });
        }
      } catch (err) {
        const aborted = err instanceof DOMException && err.name === "AbortError";
        current = {
          ...current,
          error: aborted
            ? current.content
              ? undefined
              : "Stopped before an answer was written."
            : "Something went wrong while generating the answer. Please try again.",
        };
      } finally {
        const final = current;
        update(conversation.id, (c) => ({
          ...c,
          messages: c.messages.map((m) => (m.id === final.id ? final : m)),
        }));
        setDraft(null);
        abortRef.current = null;
      }
    },
    [active, create, streaming, update],
  );

  // Abandon an in-flight answer if the page goes away.
  useEffect(() => () => abortRef.current?.abort(), []);

  const newChat = () => {
    abortRef.current?.abort();
    setActiveId(null);
    closeOverlays();
  };

  // Keep the newest message in view while it streams, unless the reader has
  // scrolled up to look at something earlier.
  const scrollRef = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  useEffect(() => {
    const el = scrollRef.current;
    // Only for a thread: on the empty state this would jump past the heading.
    if (el && pinned.current && messages.length > 0) el.scrollTop = el.scrollHeight;
  }, [messages.length, draft?.message.content]);
  useEffect(() => {
    pinned.current = true;
  }, [activeId]);

  return (
    <div className="flex h-dvh overflow-hidden bg-bg text-fg">
      {/* Left: conversation history */}
      {leftOpen && !isDesktop && (
        <div className="fixed inset-0 z-30 bg-black/30 backdrop-blur-[1px]" onClick={() => setLeftOpen(false)} aria-hidden />
      )}
      <div
        className={`${
          isDesktop ? "relative" : "fixed inset-y-0 left-0 z-40 shadow-xl"
        } h-full shrink-0 border-r border-line transition-[margin,transform] duration-200 ${
          leftOpen ? "" : isDesktop ? "-ml-72" : "-translate-x-full"
        }`}
      >
        <Sidebar
          conversations={conversations}
          hydrated={hydrated}
          activeId={activeId}
          onSelect={(id) => {
            setActiveId(id);
            closeOverlays();
          }}
          onNew={newChat}
          onRename={rename}
          onDelete={(id) => {
            if (id === activeId) newChat();
            remove(id);
          }}
          onClose={() => setLeftOpen(false)}
        />
      </div>

      {/* Centre: the conversation */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-1 px-2 sm:px-3">
          {!leftOpen && (
            <>
              <IconButton label="Open sidebar" onClick={() => setLeftOpen(true)}>
                <PanelLeft size={18} />
              </IconButton>
              <IconButton label="New chat" onClick={newChat}>
                <SquarePen size={17} />
              </IconButton>
            </>
          )}
          <h1 className="min-w-0 flex-1 truncate px-2 text-sm font-medium text-fg/90">
            {active?.title ?? "New chat"}
          </h1>
          <div className="hidden sm:block">
            <DemoBadge />
          </div>
          <Link
            href="/analytics"
            aria-label="System analytics"
            title="System analytics"
            className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-fg/[0.06] hover:text-fg"
          >
            <BarChart3 size={18} />
          </Link>
          <IconButton
            label={rightOpen ? "Hide documents" : "Show documents"}
            active={rightOpen}
            onClick={() => setRightOpen((o) => !o)}
          >
            <Library size={18} />
          </IconButton>
        </header>

        <div
          ref={scrollRef}
          onScroll={(e) => {
            const el = e.currentTarget;
            pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
          }}
          className="scrollbar-thin flex flex-1 flex-col overflow-y-auto"
        >
          {!active || messages.length === 0 ? (
            <EmptyState onPick={send} />
          ) : (
            <div className="mx-auto w-full max-w-3xl space-y-8 px-4 py-6 sm:px-6" aria-live="polite">
              {messages.map((m) =>
                m.role === "user" ? (
                  <UserMessage key={m.id} message={m} />
                ) : (
                  <AssistantMessage
                    key={m.id}
                    message={m}
                    streaming={draft?.message.id === m.id}
                    onOpenCitation={openCitation}
                  />
                ),
              )}
            </div>
          )}
        </div>

        <Composer
          streaming={streaming}
          onSend={send}
          onStop={() => abortRef.current?.abort()}
          autoFocusKey={isDesktop ? activeId ?? "new" : null}
        />
      </main>

      {/* Right: documents */}
      {rightOpen && !isWide && (
        <div className="fixed inset-0 z-30 bg-black/30 backdrop-blur-[1px]" onClick={() => setRightOpen(false)} aria-hidden />
      )}
      {rightOpen && (
        <div
          className={`${
            isWide ? "relative w-[440px]" : "fixed inset-y-0 right-0 z-40 w-full max-w-[480px] shadow-xl"
          } h-full shrink-0 border-l border-line`}
        >
          <DocumentsPanel target={docTarget} onClose={() => setRightOpen(false)} />
        </div>
      )}
    </div>
  );
}
