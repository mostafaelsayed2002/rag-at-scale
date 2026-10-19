"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { PAGE_H, PAGE_W } from "@/lib/tour";
import { SLIDES } from "./slides";
import "./tour.css";

/** Open as soon as the app opens, on every visit; `show` reopens it later. */
export function useProjectTour() {
  const [open, setOpen] = useState(true);
  return { open, show: useCallback(() => setOpen(true), []), close: useCallback(() => setOpen(false), []) };
}

export function ProjectTour({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [index, setIndex] = useState(0);
  const closeRef = useRef<HTMLButtonElement>(null);
  const touchX = useRef<number | null>(null);
  const last = SLIDES.length - 1;

  const go = useCallback((i: number) => setIndex(Math.max(0, Math.min(last, i))), [last]);

  // Focus the close button, so the keyboard works at once.
  useEffect(() => {
    if (open) closeRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setIndex(0);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") setIndex((i) => Math.min(last, i + 1));
      else if (e.key === "ArrowLeft") setIndex((i) => Math.max(0, i - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose, last]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="About this project"
      className="tour-root fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/30 backdrop-blur-[2px]"
      onClick={(e) => e.target === e.currentTarget && onClose()}
      onTouchStart={(e) => (touchX.current = e.touches[0].clientX)}
      onTouchEnd={(e) => {
        if (touchX.current === null) return;
        const dx = e.changedTouches[0].clientX - touchX.current;
        if (Math.abs(dx) > 50) go(index + (dx < 0 ? 1 : -1));
        touchX.current = null;
      }}
    >
      <div
        className="relative overflow-hidden rounded-2xl border border-line bg-bg shadow-2xl"
        style={{ width: `calc(${PAGE_W}px * var(--tour-scale))`, height: `calc(${PAGE_H}px * var(--tour-scale))` }}
        onClick={(e) => {
          // "Try it live" links point at this site: just close the tour.
          if ((e.target as HTMLElement).closest("[data-tour-close]")) {
            e.preventDefault();
            onClose();
          }
        }}
      >
        <div
          key={index}
          className="tour-slide origin-top-left"
          style={{ width: PAGE_W, height: PAGE_H, transform: "scale(var(--tour-scale))" }}
          dangerouslySetInnerHTML={{ __html: `<section class="page">${SLIDES[index]}</section>` }}
        />

        <button ref={closeRef} type="button" onClick={onClose} aria-label="Close" className={`${CONTROL} right-3 top-3 h-9 w-9`}>
          <X size={18} />
        </button>
        {index > 0 && (
          <button type="button" onClick={() => go(index - 1)} aria-label="Previous page" className={`${CONTROL} left-3 top-1/2 h-10 w-10 -translate-y-1/2`}>
            <ChevronLeft size={20} />
          </button>
        )}
        {index < last && (
          <button type="button" onClick={() => go(index + 1)} aria-label="Next page" className={`${CONTROL} right-3 top-1/2 h-10 w-10 -translate-y-1/2`}>
            <ChevronRight size={20} />
          </button>
        )}

        {/* Page dots, centred at the bottom between the page's footer texts. */}
        <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-2">
          <div className="flex h-8 items-center gap-1.5">
            {SLIDES.map((_, i) => (
              <button
                key={i}
                type="button"
                aria-label={`Page ${i + 1}`}
                aria-current={i === index ? "step" : undefined}
                onClick={() => go(i)}
                className={`h-1.5 rounded-full transition-all ${i === index ? "w-5 bg-accent" : "w-1.5 bg-fg/20 hover:bg-fg/40"}`}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/** The round buttons on the page: close and the arrows. */
const CONTROL =
  "absolute grid place-items-center rounded-full border border-line bg-elevated/90 text-muted shadow-md backdrop-blur transition-colors hover:bg-elevated hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60";
