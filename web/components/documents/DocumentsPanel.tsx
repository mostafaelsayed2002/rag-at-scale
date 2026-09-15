"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ChevronDown, ExternalLink, FileCode, FileText, Library, Search, X } from "lucide-react";
import { getDocument, listDocuments } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import type { DocumentContent, DocumentMeta } from "@/lib/types";
import { Badge, IconButton, Skeleton } from "../ui";

export type DocumentTarget = { documentId: string; sectionId?: string; nonce: number };

type Props = {
  target: DocumentTarget | null;
  onClose: () => void;
};

export function DocumentsPanel({ target, onClose }: Props) {
  const [documents, setDocuments] = useState<DocumentMeta[] | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ sectionId?: string; nonce: number } | null>(null);

  useEffect(() => {
    listDocuments().then(setDocuments).catch(() => setDocuments([]));
  }, []);

  // A citation click arrives as a new target; open that document at that spot.
  useEffect(() => {
    if (!target) return;
    setOpenId(target.documentId);
    setFocus({ sectionId: target.sectionId, nonce: target.nonce });
  }, [target]);

  return (
    <aside aria-label="Documents" className="flex h-full w-full flex-col bg-elevated">
      {openId ? (
        <DocumentViewer
          key={openId}
          documentId={openId}
          focus={focus}
          onBack={() => {
            setOpenId(null);
            setFocus(null);
          }}
          onClose={onClose}
        />
      ) : (
        <DocumentList documents={documents} onOpen={(id) => setOpenId(id)} onClose={onClose} />
      )}
    </aside>
  );
}

function DocumentList({
  documents,
  onOpen,
  onClose,
}: {
  documents: DocumentMeta[] | null;
  onOpen: (id: string) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [collection, setCollection] = useState("All");

  const collections = useMemo(
    () => ["All", ...Array.from(new Set((documents ?? []).map((d) => d.collection)))],
    [documents],
  );

  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matching = (documents ?? []).filter(
      (d) =>
        (collection === "All" || d.collection === collection) &&
        (!q || `${d.title} ${d.shortTitle} ${d.identifier}`.toLowerCase().includes(q)),
    );
    const map = new Map<string, DocumentMeta[]>();
    for (const d of matching) map.set(d.collection, [...(map.get(d.collection) ?? []), d]);
    return Array.from(map.entries());
  }, [documents, query, collection]);

  const totalChunks = (documents ?? []).reduce((sum, d) => sum + d.chunkCount, 0);

  return (
    <>
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2">
          <Library size={17} className="text-muted" aria-hidden />
          <h2 className="text-sm font-semibold">Documents</h2>
          {documents && (
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
            placeholder="Filter by title or identifier"
            aria-label="Filter documents"
            className="w-full bg-transparent outline-none placeholder:text-subtle"
          />
        </label>
        <div className="scrollbar-thin -mx-1 flex gap-1.5 overflow-x-auto px-1 pb-0.5" role="group" aria-label="Collection">
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

      <div className="scrollbar-thin flex-1 overflow-y-auto px-2 py-2">
        {!documents ? (
          <div className="space-y-2 p-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : grouped.length === 0 ? (
          <p className="px-4 pt-8 text-center text-sm text-subtle">No documents match.</p>
        ) : (
          grouped.map(([group, docs]) => (
            <section key={group} className="pb-2">
              <h3 className="px-2 pb-1 pt-2 text-[11px] font-medium uppercase tracking-wide text-subtle">{group}</h3>
              <ul>
                {docs.map((d) => {
                  const Icon = d.format === "md" ? FileCode : FileText;
                  return (
                    <li key={d.id}>
                      <button
                        type="button"
                        onClick={() => onOpen(d.id)}
                        className="flex w-full items-start gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-fg/[0.04] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
                      >
                        <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-md bg-panel text-muted">
                          <Icon size={16} aria-hidden />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-sm font-medium">{d.title}</span>
                          <span className="mt-0.5 flex items-center gap-1.5 text-xs text-muted">
                            <span className="truncate">{d.identifier}</span>
                            <span aria-hidden>·</span>
                            <span className="shrink-0">
                              {d.pageCount ? `${d.pageCount} pages` : `${d.chunkCount} chunks`}
                            </span>
                          </span>
                        </span>
                        <Badge>{d.format.toUpperCase()}</Badge>
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))
        )}
      </div>
    </>
  );
}

function DocumentViewer({
  documentId,
  focus,
  onBack,
  onClose,
}: {
  documentId: string;
  focus: { sectionId?: string; nonce: number } | null;
  onBack: () => void;
  onClose: () => void;
}) {
  const [doc, setDoc] = useState<DocumentContent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [outlineOpen, setOutlineOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    getDocument(documentId)
      .then((d) => !cancelled && setDoc(d))
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Could not load the document"));
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  // Scroll to and flash the cited section. Runs again for the same section
  // when the citation is clicked twice, because the nonce changes.
  useEffect(() => {
    if (!doc || !focus?.sectionId) return;
    const el = scrollRef.current?.querySelector<HTMLElement>(`[data-section="${focus.sectionId}"]`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    el.classList.remove("cite-target");
    void el.offsetWidth; // restart the animation
    el.classList.add("cite-target");
  }, [doc, focus]);

  const jumpTo = (sectionId: string) => {
    const el = scrollRef.current?.querySelector<HTMLElement>(`[data-section="${sectionId}"]`);
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
    setOutlineOpen(false);
  };

  return (
    <>
      <header className="flex h-14 shrink-0 items-center gap-1 border-b border-line px-2">
        <IconButton label="Back to documents" onClick={onBack}>
          <ArrowLeft size={18} />
        </IconButton>
        <div className="min-w-0 flex-1 px-1">
          {doc ? (
            <>
              <h2 className="truncate text-sm font-semibold">{doc.shortTitle}</h2>
              <p className="truncate text-xs text-muted">{doc.identifier}</p>
            </>
          ) : (
            <Skeleton className="h-4 w-40" />
          )}
        </div>
        {doc && (
          <a
            href={doc.sourceUrl}
            target="_blank"
            rel="noreferrer"
            aria-label="Open original source"
            title="Open original source"
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
      ) : !doc ? (
        <div className="space-y-3 p-5">
          <Skeleton className="h-6 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="mt-6 h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : (
        <>
          <div className="border-b border-line px-5 py-4">
            <h1 className="text-balance text-base font-semibold leading-snug">{doc.title}</h1>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              <Badge tone="accent">{doc.collection}</Badge>
              <Badge>{doc.format.toUpperCase()}</Badge>
              {doc.pageCount && <Badge>{doc.pageCount} pages</Badge>}
              <Badge>{doc.chunkCount} chunks</Badge>
              <span className="text-xs text-subtle">Published {formatDate(doc.publishedAt)}</span>
            </div>
            <button
              type="button"
              onClick={() => setOutlineOpen((o) => !o)}
              aria-expanded={outlineOpen}
              className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-muted hover:text-fg"
            >
              <ChevronDown size={14} className={`transition-transform ${outlineOpen ? "rotate-180" : ""}`} aria-hidden />
              {doc.sections.length} sections
            </button>
            {outlineOpen && (
              <ul className="mt-2 space-y-0.5 border-l border-line pl-3">
                {doc.sections.map((s) => (
                  <li key={s.id}>
                    <button
                      type="button"
                      onClick={() => jumpTo(s.id)}
                      className="w-full truncate py-0.5 text-left text-xs text-muted hover:text-accent"
                    >
                      {s.heading}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div ref={scrollRef} className="scrollbar-thin flex-1 overflow-y-auto px-5 py-5">
            <p className="mb-5 rounded-lg bg-warn/10 px-3 py-2 text-xs leading-relaxed text-warn">
              Mock excerpts: short paraphrases of the source, not official text. Page numbers are approximate.
            </p>
            {/* Bottom padding lets the last section scroll to the top when cited. */}
            <div className="space-y-6 pb-[60vh]">
              {doc.sections.map((s, i) => {
                const newPage = s.page != null && s.page !== doc.sections[i - 1]?.page;
                return (
                  <div key={s.id} className="scroll-mt-4">
                    {newPage && (
                      <div className="mb-3 flex items-center gap-3 text-[11px] font-medium uppercase tracking-wide text-subtle">
                        <span className="h-px flex-1 bg-line" />
                        Page {s.page}
                        <span className="h-px flex-1 bg-line" />
                      </div>
                    )}
                    <section data-section={s.id} className="-mx-2 px-2 py-1">
                      <h3 className="text-sm font-semibold">{s.heading}</h3>
                      <div className="mt-2 space-y-2 text-[14px] leading-relaxed text-fg/85">
                        {s.paragraphs.map((p, j) => (
                          <p key={j}>{p}</p>
                        ))}
                      </div>
                    </section>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </>
  );
}
