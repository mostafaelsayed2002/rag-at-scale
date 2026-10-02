"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { ArrowLeft, ExternalLink, FileText, Library, Search, X } from "lucide-react";
import { documentFileUrl, getDocument, listDocuments } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { DocumentDetail, DocumentPage, DocumentSummary } from "@/lib/types";
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
  const [open, setOpen] = useState<DocumentTarget | null>(null);

  // A citation click arrives as a new target: open that document at that page.
  useEffect(() => {
    if (target) setOpen(target);
  }, [target]);

  return (
    <aside aria-label="Documents" className="flex h-full min-h-0 flex-col bg-elevated">
      {open ? (
        <DocumentView target={open} onBack={() => setOpen(null)} onClose={onClose} />
      ) : (
        <DocumentList onOpen={(docId) => setOpen({ docId, nonce: Date.now() })} onClose={onClose} />
      )}
    </aside>
  );
}

// The corpus has tens of thousands of acts: the API searches and pages them,
// and the panel asks for one page at a time.
const PAGE_SIZE = 50;
const SEARCH_DELAY_MS = 300;

function DocumentList({ onOpen, onClose }: { onOpen: (docId: string) => void; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState(""); // `query` once typing pauses
  const [collection, setCollection] = useState<string | null>(null);
  const [page, setPage] = useState<DocumentPage | null>(null);
  const [items, setItems] = useState<DocumentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Ask the API only when typing pauses, not on every keystroke.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(query.trim()), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [query]);

  // A new search or filter starts again from the first page. `cancelled`
  // drops the answer to an older request that arrives after a newer one.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listDocuments({ q: search || undefined, collection: collection ?? undefined, limit: PAGE_SIZE })
      .then((p) => {
        if (cancelled) return;
        setPage(p);
        setItems(p.items);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Could not load documents"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [search, collection]);

  const loadMore = () => {
    setLoadingMore(true);
    listDocuments({
      q: search || undefined,
      collection: collection ?? undefined,
      limit: PAGE_SIZE,
      offset: items.length,
    })
      .then((p) => setItems((prev) => [...prev, ...p.items]))
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load more"))
      .finally(() => setLoadingMore(false));
  };

  const filters: { label: string; value: string | null; count?: number }[] = [
    { label: "All", value: null, count: page?.corpus.documents },
    ...(page?.collections ?? []).map((c) => ({ label: c.name, value: c.name, count: c.count })),
  ];

  return (
    <>
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2">
          <Library size={17} className="text-muted" aria-hidden />
          <h2 className="text-sm font-semibold">Documents</h2>
          {page && (
            <span className="text-xs text-subtle">
              {formatNumber(page.corpus.documents)} acts · {formatNumber(page.corpus.chunks)} chunks
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
            placeholder="Search titles or numbers, e.g. 2016/679"
            aria-label="Search documents"
            className="w-full bg-transparent outline-none placeholder:text-subtle"
          />
        </label>
        <div
          className="scrollbar-thin -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-0.5"
          role="group"
          aria-label="Collection"
        >
          {filters.map((f) => (
            <button
              key={f.label}
              type="button"
              onClick={() => setCollection(f.value)}
              aria-pressed={collection === f.value}
              className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                collection === f.value
                  ? "border-accent bg-accent text-accent-fg"
                  : "border-line text-muted hover:border-fg/20 hover:text-fg"
              }`}
            >
              {f.label}
              {f.count != null && <span className="ml-1 opacity-70">{formatNumber(f.count)}</span>}
            </button>
          ))}
        </div>
      </div>

      <div className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-2 py-2">
        {loading ? (
          <div className="space-y-2 p-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : error ? (
          <p className="px-4 pt-8 text-center text-sm text-bad">{error}</p>
        ) : items.length === 0 ? (
          <p className="px-4 pt-8 text-center text-sm text-subtle">
            {page?.corpus.documents === 0 ? "No documents ingested yet." : "Nothing matches."}
          </p>
        ) : (
          <>
            <p className="px-2 pb-1 pt-1 text-[11px] font-medium uppercase tracking-wide text-subtle">
              {formatNumber(page?.total ?? 0)} {search ? "matching" : "acts"} · newest first
            </p>
            <ul>
              {items.map((d) => (
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
                      <span className="line-clamp-2 text-sm font-medium">{d.title ?? d.doc_id}</span>
                      <span className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
                        <span className="truncate">{d.collection ?? d.document_type ?? "document"}</span>
                        {d.publication_date && (
                          <>
                            <span aria-hidden>·</span>
                            <span className="shrink-0">{d.publication_date.slice(0, 4)}</span>
                          </>
                        )}
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
            {page && items.length < page.total && (
              <div className="px-2 pb-3 pt-2">
                <button
                  type="button"
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="w-full rounded-lg border border-line px-3 py-2 text-xs font-medium text-muted transition-colors hover:border-fg/20 hover:text-fg disabled:opacity-60"
                >
                  {loadingMore
                    ? "Loading…"
                    : `Load more · showing ${formatNumber(items.length)} of ${formatNumber(page.total)}`}
                </button>
              </div>
            )}
          </>
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
                {doc.publication_date ? ` · ${doc.publication_date}` : ""}
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
