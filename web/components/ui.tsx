"use client";

import { forwardRef } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  active?: boolean;
  children: ReactNode;
};

/** Square icon button. The label is required so every icon has an accessible name. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, active, className = "", children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      aria-label={label}
      title={label}
      className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted transition-colors hover:bg-fg/[0.06] hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60 disabled:pointer-events-none disabled:opacity-40 ${
        active ? "bg-fg/[0.07] text-fg" : ""
      } ${className}`}
      {...props}
    >
      {children}
    </button>
  );
});

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "accent" | "good" | "warn" | "bad" }) {
  const tones = {
    neutral: "bg-fg/[0.06] text-muted",
    accent: "bg-accent-soft text-accent",
    good: "bg-good/10 text-good",
    warn: "bg-warn/10 text-warn",
    bad: "bg-bad/10 text-bad",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium leading-none ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-md bg-fg/[0.06] ${className}`} />;
}
