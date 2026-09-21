"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import { ArrowLeft, ExternalLink, FileText, Library, Search, X } from "lucide-react";
import { documentFileUrl, getDocument, listDocuments } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { DocumentDetail, DocumentSummary } from "@/lib/types";
import { Badge, IconButton, Skeleton } from "../ui";

// PDF.js touches browser APIs at import time, so it must not run during
// server rendering.
const PdfViewer = dynamic(() => import("./PdfViewer").then((m) => m.PdfViewer), {
  ssr: false,
  loading: () => <Skeleton className="m-3 h-[70vh]" />,
});

export type DocumentTarget = {
  docId: string;
  page?: number;
  quote?: string;
  nonce: number;
};

type Props = {
  target: DocumentTarget | null;
  onClose: () => void;
};

export function DocumentsPanel({ target, onClose }: Props) {
  const [documents, setDocuments] = useState<DocumentSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<DocumentTarget | null>(null);

  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch((e) => {
        setDocuments([]);
        setError(e instanceof Error ? e.message : "Could not load documents");
      });
  }, []);

  // A citation click arrives as a new target: open that document at that page.
  useEffect(() => {
    if (target) setOpen(target);
  }, [target]);

  return (
    <aside aria-label="Documents" className="flex h-full min-h-0 flex-col bg-elevated">
      {open ? (
        <DocumentView target={open} onBack={() => setOpen(null)} onClose={onClose} />
      ) : (
        <DocumentList
          documents={documents}
          error={error}
          onOpen={(docId) => setOpen({ docId, nonce: Date.now() })}
          onClose={onClose}
        />
      )}
    </aside>
  );
}

function DocumentList({
  documents,
  error,
  onOpen,
  onClose,
}: {
  documents: DocumentSummary[] | null;
  error: string | null;
  onOpen: (docId: string) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [collection, setCollection] = useState("All");

  const collections = useMemo(
    () => ["All", ...Array.from(new Set((documents ?? []).map((d) => d.collection ?? "other")))],
    [documents],
  );

  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matching = (documents ?? []).filter((d) => {
      const group = d.collection ?? "other";
      const haystack = `${d.title ?? ""} ${d.doc_id}`.toLowerCase();
      return (collection === "All" || group === collection) && (!q || haystack.includes(q));
    });
    const map = new Map<string, DocumentSummary[]>();
    for (const d of matching) {
      const group = d.collection ?? "other";
      map.set(group, [...(map.get(group) ?? []), d]);
    }
    return Array.from(map.entries());
  }, [documents, query, collection]);

  const totalChunks = (documents ?? []).reduce((sum, d) => sum + (d.chunk_count ?? 0), 0);

  return (
    <>
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2">
          <Library size={17} className="text-muted" aria-hidden />
          <h2 className="text-sm font-semibold">Documents</h2>
          {documents && documents.length > 0 && (
            <span className="text-xs text-subtle">
              {documents.length} · {formatNumber(totalChunks)} chunks
            </span>
          )}
        </div>
        <IconButton label="Close documents" onClick={onClose}>
          <X size={18} />
        </IconButton>
      </header>

      <div className="space-y-3 border-b border-line px-4 py-3">
        <label className="flex items-center gap-2 rounded-lg border border-line bg-bg px-2.5 py-1.5 text-sm focus-within:border-accent/50">
          <Search size={15} className="text-subtle" aria-hidden />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by title"
            aria-label="Filter documents"
            className="w-full bg-transparent outline-none placeholder:text-subtle"
          />
        </label>
        <div
          className="scrollbar-thin -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-0.5"
          role="group"
          aria-label="Collection"
        >
          {collections.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => setCollection(c)}
              aria-pressed={collection === c}
              className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                collection === c
                  ? "border-accent bg-accent text-accent-fg"
                  : "border-line text-muted hover:border-fg/20 hover:text-fg"
              }`}
            >
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {!documents ? (
          <div className="space-y-2 p-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : error ? (
          <p className="px-4 pt-8 text-center text-sm text-bad">{error}</p>
        ) : grouped.length === 0 ? (
          <p className="px-4 pt-8 text-center text-sm text-subtle">
            {documents.length === 0 ? "No documents ingested yet." : "Nothing matches."}
          </p>
        ) : (
          grouped.map(([group, docs]) => (
            <section key={group} className="pb-2">
              <h3 className="px-2 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-subtle">
                {group}
              </h3>
              <ul>
                {docs.map((d) => (
                  <li key={d.doc_id}>
                    <button
                      type="button"
                      onClick={() => onOpen(d.doc_id)}
                      className="flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-fg/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
                    >
                      <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-md bg-panel text-muted">
                        <FileText size={16} aria-hidden />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium">
                          {d.title ?? d.doc_id}
                        </span>
                        <span className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
                          <span className="truncate">{d.document_type ?? "document"}</span>
                          {d.page_count != null && (
                            <>
                              <span aria-hidden>·</span>
                              <span className="shrink-0">{d.page_count} pages</span>
                            </>
                          )}
                        </span>
                      </span>
                      <Badge>PDF</Badge>
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
      </div>
    </>
  );
}

function DocumentView({
  target,
  onBack,
  onClose,
}: {
  target: DocumentTarget;
  onBack: () => void;
  onClose: () => void;
}) {
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setDoc(null);
    getDocument(target.docId)
      .then((d) => !cancelled && setDoc(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Not found"));
    return () => {
      cancelled = true;
    };
  }, [target.docId]);

  return (
    <>
      <header className="flex h-14 shrink-0 items-center gap-1 border-b border-line px-2">
        <IconButton label="Back to documents" onClick={onBack}>
          <ArrowLeft size={18} />
        </IconButton>
        <div className="min-w-0 flex-1 px-1">
          {doc ? (
            <>
              <h2 className="truncate text-sm font-semibold">{doc.title ?? doc.doc_id}</h2>
              <p className="truncate text-xs text-muted">
                {doc.celex_number ?? doc.document_type ?? doc.collection}
                {target.page ? ` · cited on page ${target.page}` : ""}
              </p>
            </>
          ) : (
            <Skeleton className="h-4 w-40" />
          )}
        </div>
        {doc?.source_url && (
          <a
            href={doc.source_url}
            target="_blank"
            rel="noreferrer"
            aria-label="Open the official source"
            title="Open the official source"
            className="grid h-9 w-9 place-items-center rounded-lg text-muted transition-colors hover:bg-fg/[0.06] hover:text-fg"
          >
            <ExternalLink size={16} />
          </a>
        )}
        <IconButton label="Close documents" onClick={onClose}>
          <X size={18} />
        </IconButton>
      </header>

      {error ? (
        <p className="p-6 text-sm text-bad">{error}</p>
      ) : doc && !doc.has_file ? (
        <p className="p-6 text-sm text-muted">
          This document has no PDF on the server, so it cannot be displayed.
        </p>
      ) : (
        <PdfViewer
          fileUrl={documentFileUrl(target.docId)}
          page={target.page ?? 1}
          quote={target.quote}
          nonce={target.nonce}
        />
      )}
    </>
  );
}
