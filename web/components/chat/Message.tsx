"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Check, Clock, Copy, Database, FileCode, FileText, Hash, Zap } from "lucide-react";
import { MOCK_DOCUMENTS } from "@/lib/mock/documents";
import { formatMs } from "@/lib/format";
import type { Citation, Message as MessageType } from "@/lib/types";
import { IconButton } from "../ui";

export type OpenCitation = (citation: Citation) => void;

// Titles for citation cards. Taken from the mock corpus today; the backend
// should include a document title on each citation instead.
const DOC_TITLES = new Map(MOCK_DOCUMENTS.map((d) => [d.id, { title: d.shortTitle, format: d.format }]));

export function UserMessage({ message }: { message: MessageType }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-fg/[0.07] px-4 py-2.5 text-[15px] leading-relaxed">
        {message.content}
      </div>
    </div>
  );
}

export function AssistantMessage({
  message,
  streaming,
  onOpenCitation,
}: {
  message: MessageType;
  streaming: boolean;
  onOpenCitation: OpenCitation;
}) {
  const citations = message.citations ?? [];
  const waiting = streaming && !message.content;

  return (
    <div className="flex gap-3">
      <div
        aria-hidden
        className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full bg-accent text-[11px] font-bold text-accent-fg"
      >
        R
      </div>
      <div className="min-w-0 flex-1 space-y-3">
        {waiting ? (
          <Thinking hasSources={citations.length > 0} />
        ) : (
          <AnswerBody content={message.content} citations={citations} streaming={streaming} onOpenCitation={onOpenCitation} />
        )}

        {message.error && (
          <p className="flex items-center gap-2 rounded-lg border border-bad/30 bg-bad/5 px-3 py-2 text-sm text-bad">
            <AlertTriangle size={15} aria-hidden />
            {message.error}
          </p>
        )}

        {citations.length > 0 && <SourceList citations={citations} onOpenCitation={onOpenCitation} />}

        {!streaming && message.content && <MessageFooter message={message} />}
      </div>
    </div>
  );
}

function Thinking({ hasSources }: { hasSources: boolean }) {
  return (
    <div className="flex items-center gap-2 py-1 text-sm text-muted" role="status">
      <span className="flex gap-1" aria-hidden>
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 animate-bounce rounded-full bg-subtle"
            style={{ animationDelay: `${i * 120}ms` }}
          />
        ))}
      </span>
      {hasSources ? "Writing the answer…" : "Searching the corpus…"}
    </div>
  );
}

/** Turns [n] markers into links the markdown renderer hands to CitationMarker. */
function linkCitations(content: string) {
  return content.replace(/\[(\d+)\](?!\()/g, "[$1](#cite-$1)");
}

function AnswerBody({
  content,
  citations,
  streaming,
  onOpenCitation,
}: {
  content: string;
  citations: Citation[];
  streaming: boolean;
  onOpenCitation: OpenCitation;
}) {
  const markdown = useMemo(() => linkCitations(content), [content]);

  return (
    <div className={`prose-answer text-[15px] ${streaming ? "streaming-caret" : ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            if (href?.startsWith("#cite-")) {
              const citation = citations.find((c) => c.index === Number(href.slice(6)));
              if (citation) return <CitationMarker citation={citation} onOpen={onOpenCitation} />;
              return <sup className="text-subtle">{children}</sup>;
            }
            return (
              <a href={href} target="_blank" rel="noreferrer" className="text-accent underline underline-offset-2">
                {children}
              </a>
            );
          },
        }}
      >
        {markdown}
      </ReactMarkdown>
    </div>
  );
}

function CitationMarker({ citation, onOpen }: { citation: Citation; onOpen: OpenCitation }) {
  const doc = DOC_TITLES.get(citation.documentId);
  return (
    <span className="group relative inline-block align-baseline">
      <button
        type="button"
        onClick={() => onOpen(citation)}
        aria-label={`Source ${citation.index}: ${doc?.title ?? citation.documentId}, ${citation.locator}`}
        className="relative mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-px items-center justify-center rounded-md bg-accent-soft px-1 text-[11px] font-semibold leading-none text-accent transition-colors before:absolute before:-inset-1.5 before:content-[''] hover:bg-accent hover:text-accent-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
      >
        {citation.index}
      </button>
      <span
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-30 mb-2 w-72 -translate-x-1/2 rounded-lg border border-line bg-elevated p-3 text-left opacity-0 shadow-lg transition-opacity group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100"
      >
        <span className="block text-xs font-semibold text-fg">
          {doc?.title} · {citation.locator}
          {citation.page != null && <span className="font-normal text-muted"> · p. {citation.page}</span>}
        </span>
        <span className="mt-1 line-clamp-3 block text-xs font-normal leading-relaxed text-muted">{citation.snippet}</span>
      </span>
    </span>
  );
}

function SourceList({ citations, onOpenCitation }: { citations: Citation[]; onOpenCitation: OpenCitation }) {
  return (
    <div>
      <h3 className="mb-2 text-[11px] font-medium uppercase tracking-wide text-subtle">Sources</h3>
      <ol className="grid gap-2 sm:grid-cols-2">
        {citations.map((c) => {
          const doc = DOC_TITLES.get(c.documentId);
          const Icon = doc?.format === "md" ? FileCode : FileText;
          return (
            <li key={c.index}>
              <button
                type="button"
                onClick={() => onOpenCitation(c)}
                className="group flex w-full items-start gap-2.5 rounded-lg border border-line bg-elevated px-3 py-2 text-left transition-colors hover:border-accent/40 hover:bg-accent-soft/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
              >
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-md bg-accent-soft text-[11px] font-semibold text-accent">
                  {c.index}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5 text-sm font-medium">
                    <Icon size={13} className="shrink-0 text-subtle" aria-hidden />
                    <span className="truncate">{doc?.title ?? c.documentId}</span>
                  </span>
                  <span className="mt-0.5 block truncate text-xs text-muted">
                    {c.locator}
                    {c.page != null && ` · page ${c.page}`}
                  </span>
                </span>
                <span className="shrink-0 pt-0.5 font-mono text-[11px] tabular-nums text-subtle" title="Rerank score">
                  {c.score.toFixed(2)}
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

const CACHE_LABEL = { none: null, embedding: "Embedding cached", semantic: "Semantic cache hit", response: "Response cache hit" };

function MessageFooter({ message }: { message: MessageType }) {
  const [copied, setCopied] = useState(false);
  const m = message.metrics;

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be unavailable in insecure contexts; nothing useful to do.
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-subtle">
      <IconButton label={copied ? "Copied" : "Copy answer"} onClick={copy} className="-ml-2 h-7 w-7">
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </IconButton>
      {m && (
        <>
          <span className="inline-flex items-center gap-1" title="End-to-end latency">
            <Clock size={12} aria-hidden />
            {formatMs(m.latencyMs)}
          </span>
          <span className="inline-flex items-center gap-1" title="Prompt and completion tokens">
            <Hash size={12} aria-hidden />
            {m.promptTokens + m.completionTokens} tokens
          </span>
          <span className="inline-flex items-center gap-1" title="Chunks retrieved before reranking">
            <Database size={12} aria-hidden />
            {m.retrievedChunks} retrieved
          </span>
          {CACHE_LABEL[m.cacheHit] && (
            <span className="inline-flex items-center gap-1 text-good">
              <Zap size={12} aria-hidden />
              {CACHE_LABEL[m.cacheHit]}
            </span>
          )}
        </>
      )}
    </div>
  );
}
