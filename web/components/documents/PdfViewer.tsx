"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import type { TextContent, TextItem } from "pdfjs-dist/types/src/display/api";
import { ChevronLeft, ChevronRight, Minus, Plus } from "lucide-react";
import "react-pdf/dist/esm/Page/TextLayer.css";
import "react-pdf/dist/esm/Page/AnnotationLayer.css";
import { IconButton, Skeleton } from "../ui";

// The worker parses the PDF off the main thread. Served from public/ rather
// than bundled: Next's minifier rejects the worker's module syntax. The copy
// script keeps it in step with the installed pdfjs-dist.
pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

type Props = {
  fileUrl: string;
  /** Page to open at, 1-based. */
  page: number;
  /** Passage to highlight on that page, if it can be found. */
  quote?: string;
  /** Changes whenever the same citation is clicked again. */
  nonce: number;
};

const normalise = (text: string) => text.replace(/\s+/g, " ").trim().toLowerCase();

export function PdfViewer({ fileUrl, page, quote, nonce }: Props) {
  const [pageCount, setPageCount] = useState(0);
  const [current, setCurrent] = useState(page);
  const [scale, setScale] = useState(1);
  const [width, setWidth] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Follow the citation: a new target moves to its page, even if the reader
  // has since paged away.
  useEffect(() => setCurrent(page), [page, nonce]);

  // Render at the panel's width, so the page fills it at any window size.
  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width - 24));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  // The needle for highlighting. Only the opening of the passage is used: a
  // chunk can run past the end of the page, and the start is what was cited.
  const needle = useMemo(() => (quote ? normalise(quote).slice(0, 400) : ""), [quote]);

  // Character range of the cited passage within the page's text, and where
  // each text fragment sits in that same text.
  const spans = useRef<{ start: number; end: number }[]>([]);
  const [range, setRange] = useState<{ from: number; to: number } | null>(null);
  const rangeRef = useRef<{ from: number; to: number } | null>(null);

  // The text layer renders before the passage is located and does not redraw
  // when it is, so the page is keyed on the range and remounts once it is
  // known. Setting the same range twice is skipped, or the remount would
  // locate again and loop.
  const applyRange = useCallback((next: { from: number; to: number } | null) => {
    const current = rangeRef.current;
    const same =
      (current === null && next === null) ||
      (current !== null && next !== null && current.from === next.from && current.to === next.to);
    if (same) return;
    rangeRef.current = next;
    setRange(next);
  }, []);

  /**
   * Locate the passage once, when the page's text is ready.
   *
   * Fragment-by-fragment matching does not work: PDF.js splits a line into
   * short pieces, and a common word like "generated" then lights up all over
   * the page. Instead the fragments are joined into one string, the passage's
   * opening and closing words are found in it, and everything between is the
   * highlighted region.
   */
  const locatePassage = useCallback(
    ({ items }: TextContent) => {
      // Marked-content entries carry no text; only TextItems have a string.
      const texts = items.filter((item): item is TextItem => "str" in item);

      let offset = 0;
      spans.current = texts.map((item) => {
        const start = offset;
        offset += normalise(item.str).length + 1; // +1 for the joining space
        return { start, end: offset - 1 };
      });

      if (!needle) {
        applyRange(null);
        return;
      }

      const pageText = texts.map((item) => normalise(item.str)).join(" ");
      const words = needle.split(" ").filter(Boolean);

      // Try a long opening phrase first, then shorter ones, and allow the
      // probe to start a word or two in: a chunk often begins with the page
      // number or a heading fragment, which the text layer places elsewhere
      // on the page, so a probe anchored to the very first word never matches.
      let from = -1;
      outer: for (const skip of [0, 1, 2, 3]) {
        for (const size of [8, 5, 3]) {
          if (words.length < skip + size) continue;
          from = pageText.indexOf(words.slice(skip, skip + size).join(" "));
          if (from !== -1) break outer;
        }
      }
      if (from === -1) {
        applyRange(bestOverlap(pageText, words));
        return;
      }

      const tail = words.slice(-4).join(" ");
      const tailAt = pageText.indexOf(tail, from);
      // A chunk can continue onto the next page, so fall back to its length.
      const to = tailAt === -1 ? from + needle.length : tailAt + tail.length;
      applyRange({ from, to });
    },
    [needle, applyRange],
  );

  const renderText = useCallback(
    ({ itemIndex, str }: { itemIndex: number; str: string }) => {
      const span = spans.current[itemIndex];
      const inside = range && span && span.start < range.to && span.end > range.from;
      return inside ? `<mark class="cite-mark">${escapeHtml(str)}</mark>` : escapeHtml(str);
    },
    [range],
  );

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-line px-2 py-1.5">
        <div className="flex items-center gap-1">
          <IconButton
            label="Previous page"
            className="h-7 w-7"
            disabled={current <= 1}
            onClick={() => setCurrent((n) => Math.max(1, n - 1))}
          >
            <ChevronLeft size={15} />
          </IconButton>
          <span className="min-w-[5.5rem] text-center text-xs tabular-nums text-muted">
            {pageCount ? `Page ${current} of ${pageCount}` : "Loading…"}
          </span>
          <IconButton
            label="Next page"
            className="h-7 w-7"
            disabled={pageCount === 0 || current >= pageCount}
            onClick={() => setCurrent((n) => Math.min(pageCount, n + 1))}
          >
            <ChevronRight size={15} />
          </IconButton>
        </div>
        <div className="flex items-center gap-1">
          <IconButton
            label="Zoom out"
            className="h-7 w-7"
            disabled={scale <= 0.6}
            onClick={() => setScale((s) => Math.max(0.6, s - 0.2))}
          >
            <Minus size={15} />
          </IconButton>
          <span className="w-10 text-center text-xs tabular-nums text-muted">
            {Math.round(scale * 100)}%
          </span>
          <IconButton
            label="Zoom in"
            className="h-7 w-7"
            disabled={scale >= 2.4}
            onClick={() => setScale((s) => Math.min(2.4, s + 0.2))}
          >
            <Plus size={15} />
          </IconButton>
        </div>
      </div>

      <div ref={containerRef} className="scrollbar-thin min-h-0 flex-1 overflow-auto bg-panel p-3">
        {error ? (
          <p className="rounded-lg border border-bad/30 bg-bad/5 p-3 text-sm text-bad">{error}</p>
        ) : (
          <Document
            file={fileUrl}
            onLoadSuccess={({ numPages }) => {
              setPageCount(numPages);
              setError(null);
            }}
            onLoadError={(e) => setError(`Could not open the PDF: ${e.message}`)}
            loading={<Skeleton className="h-[70vh] w-full" />}
            error={null}
          >
            <Page
              key={`${current}-${nonce}-${range ? `${range.from}-${range.to}` : "none"}`}
              pageNumber={current}
              width={width > 0 ? width * scale : undefined}
              onGetTextSuccess={locatePassage}
              customTextRenderer={renderText}
              renderAnnotationLayer={false}
              loading={<Skeleton className="h-[70vh] w-full" />}
              className="mx-auto w-fit overflow-hidden rounded-md shadow-sm"
            />
          </Document>
        )}
      </div>
    </div>
  );
}

/**
 * Fallback when no phrase from the passage is found verbatim.
 *
 * Headings, footnotes and two-column layouts make PDF.js emit text in an
 * order the stored chunk does not follow, so exact phrases can fail even
 * though the passage is on the page. This slides a window of the passage's
 * length across the page and keeps the stretch sharing the most words with
 * it, which survives reordering. It gives up below half the words, rather
 * than highlighting something unrelated.
 */
function bestOverlap(pageText: string, needleWords: string[]): { from: number; to: number } | null {
  const wanted = new Set(needleWords.filter((w) => w.length > 3));
  if (wanted.size < 4) return null;

  const words: { text: string; at: number }[] = [];
  const pattern = /\S+/g;
  for (let match = pattern.exec(pageText); match; match = pattern.exec(pageText)) {
    words.push({ text: match[0], at: match.index });
  }

  const window = Math.min(needleWords.length, words.length);
  let best = { score: 0, start: 0 };
  for (let start = 0; start + window <= words.length; start++) {
    let score = 0;
    for (let i = start; i < start + window; i++) if (wanted.has(words[i].text)) score++;
    if (score > best.score) best = { score, start };
  }

  if (best.score < wanted.size * 0.5) return null;
  const first = words[best.start];
  const last = words[Math.min(best.start + window, words.length) - 1];
  return { from: first.at, to: last.at + last.text.length };
}

function escapeHtml(text: string): string {
  return text
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
