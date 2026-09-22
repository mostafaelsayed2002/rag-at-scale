"use client";

import { useId, useState } from "react";
import type { TimePoint } from "@/lib/types";

type ChartProps = {
  points: TimePoint[];
  format: (value: number) => string;
  kind?: "line" | "bar";
  height?: number;
  label: string;
};

const hourLabel = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "UTC" });

/**
 * Small dependency-free time series chart. The SVG stretches to its container;
 * text lives in HTML around it so labels never distort.
 */
export function TimeSeriesChart({ points, format, kind = "line", height = 120, label }: ChartProps) {
  const [hover, setHover] = useState<number | null>(null);
  const gradientId = useId();

  const values = points.map((p) => p.value);
  const max = Math.max(...values) * 1.1 || 1;
  const n = points.length;
  const x = (i: number) => (n === 1 ? 50 : (i / (n - 1)) * 100);
  const y = (v: number) => 100 - (v / max) * 100;

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.value)}`).join(" ");
  const area = `${line} L100,100 L0,100 Z`;
  const shown = hover ?? n - 1;

  return (
    <figure className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <figcaption className="text-xs text-muted">{hover == null ? "Latest" : hourLabel(points[shown].t)}</figcaption>
        <span className="font-mono text-sm font-medium tabular-nums">{format(points[shown].value)}</span>
      </div>
      <div
        className="relative text-accent"
        style={{ height }}
        onMouseLeave={() => setHover(null)}
        onMouseMove={(e) => {
          const rect = e.currentTarget.getBoundingClientRect();
          const i = Math.round(((e.clientX - rect.left) / rect.width) * (n - 1));
          setHover(Math.max(0, Math.min(n - 1, i)));
        }}
      >
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="h-full w-full overflow-visible" role="img" aria-label={label}>
          <defs>
            <linearGradient id={gradientId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="currentColor" stopOpacity="0.18" />
              <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[25, 50, 75].map((g) => (
            <line key={g} x1="0" x2="100" y1={g} y2={g} className="stroke-line" strokeWidth="1" vectorEffect="non-scaling-stroke" />
          ))}
          {kind === "bar" ? (
            points.map((p, i) => {
              const w = 100 / n;
              return (
                <rect
                  key={p.t}
                  x={i * w + w * 0.18}
                  width={w * 0.64}
                  y={y(p.value)}
                  height={100 - y(p.value)}
                  fill="currentColor"
                  opacity={hover == null || hover === i ? 0.85 : 0.35}
                />
              );
            })
          ) : (
            <>
              <path d={area} fill={`url(#${gradientId})`} />
              <path d={line} fill="none" stroke="currentColor" strokeWidth="2" vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
              {hover != null && (
                <line
                  x1={x(hover)}
                  x2={x(hover)}
                  y1="0"
                  y2="100"
                  stroke="currentColor"
                  strokeOpacity="0.4"
                  strokeWidth="1"
                  vectorEffect="non-scaling-stroke"
                />
              )}
            </>
          )}
        </svg>
      </div>
      <div className="flex justify-between text-[11px] text-subtle">
        <span>{hourLabel(points[0].t)}</span>
        <span>{hourLabel(points[n - 1].t)} UTC</span>
      </div>
    </figure>
  );
}

/** Horizontal bar with an optional target tick, for ratios and stage timings. */
export function Meter({
  value,
  max = 1,
  target,
  tone = "accent",
  secondary,
}: {
  value: number;
  max?: number;
  target?: number;
  tone?: "accent" | "good" | "warn" | "bad";
  secondary?: number;
}) {
  const pct = (v: number) => `${Math.min(100, (v / max) * 100)}%`;
  const tones = { accent: "bg-accent", good: "bg-good", warn: "bg-warn", bad: "bg-bad" };
  return (
    <div className="relative h-2 overflow-hidden rounded-full bg-fg/[0.07]">
      {secondary != null && <div className={`absolute inset-y-0 left-0 ${tones[tone]} opacity-30`} style={{ width: pct(secondary) }} />}
      <div className={`absolute inset-y-0 left-0 rounded-full ${tones[tone]}`} style={{ width: pct(value) }} />
      {target != null && <div className="absolute inset-y-[-2px] w-0.5 bg-fg/60" style={{ left: pct(target) }} aria-hidden />}
    </div>
  );
}
