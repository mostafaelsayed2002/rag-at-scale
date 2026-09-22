"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Clock,
  Coins,
  Database,
  Gauge,
  Hash,
  Layers,
  Zap,
} from "lucide-react";
import { getAnalytics } from "@/lib/api";
import { formatMs, formatNumber, formatPercent, formatUsd } from "@/lib/format";
import type { Analytics, TimePoint } from "@/lib/types";
import { Skeleton } from "../ui";
import { Meter, TimeSeriesChart } from "./Charts";

const WINDOWS = [
  { hours: 1, label: "1h" },
  { hours: 24, label: "24h" },
  { hours: 168, label: "7d" },
];

export function AnalyticsDashboard() {
  const [hours, setHours] = useState(24);
  const [data, setData] = useState<Analytics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    setError(null);
    getAnalytics(hours)
      .then((d) => live && setData(d))
      .catch((e) => live && setError(e instanceof Error ? e.message : "Could not load metrics"));
    return () => {
      live = false;
    };
  }, [hours]);

  return (
    <div className="min-h-dvh bg-bg text-fg">
      <header className="sticky top-0 z-10 border-b border-line bg-bg/85 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-3 px-4 sm:px-6">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-muted transition-colors hover:bg-fg/[0.05] hover:text-fg"
          >
            <ArrowLeft size={16} />
            Chat
          </Link>
          <span className="h-5 w-px bg-line" aria-hidden />
          <h1 className="flex-1 truncate text-sm font-semibold">System analytics</h1>
          <div className="flex rounded-lg border border-line p-0.5" role="group" aria-label="Time window">
            {WINDOWS.map((w) => (
              <button
                key={w.hours}
                type="button"
                onClick={() => setHours(w.hours)}
                aria-pressed={hours === w.hours}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition-colors ${
                  hours === w.hours ? "bg-fg/[0.08] text-fg" : "text-muted hover:text-fg"
                }`}
              >
                {w.label}
              </button>
            ))}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Retrieval and generation health</h2>
          <p className="mt-1 text-sm text-muted">
            Measured from every request the API served. Counters live in Redis; the history behind
            the percentiles and charts is one row per request in Postgres.
          </p>
        </div>

        {error ? (
          <p className="rounded-lg border border-bad/30 bg-bad/5 p-4 text-sm text-bad">{error}</p>
        ) : !data ? (
          <LoadingState />
        ) : data.totals.requests === 0 ? (
          <EmptyWindow />
        ) : (
          <Dashboard d={data} />
        )}
      </main>
    </div>
  );
}

function Dashboard({ d }: { d: Analytics }) {
  const t = d.totals;
  const maxStage = Math.max(...d.stages.map((s) => s.p95_ms), 1);
  const points = (key: "requests" | "p95_latency_ms" | "error_rate" | "cache_hit_rate"): TimePoint[] =>
    d.series.map((s) => ({ t: s.t, value: s[key] }));

  return (
    <>
      <section aria-label="Key metrics" className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <Kpi
          icon={<Activity size={15} />}
          label="Requests"
          value={formatNumber(t.requests)}
          sub={`over ${d.window_hours}h`}
        />
        <Kpi
          icon={<Clock size={15} />}
          label="p95 latency"
          value={formatMs(t.p95_latency_ms)}
          sub={`p50 ${formatMs(t.p50_latency_ms)} · p99 ${formatMs(t.p99_latency_ms)}`}
        />
        <Kpi
          icon={<Zap size={15} />}
          label="Cache hit rate"
          value={formatPercent(overallHitRate(d))}
          sub={`${formatNumber(savedCalls(d))} API calls avoided`}
          tone="good"
        />
        <Kpi
          icon={<AlertTriangle size={15} />}
          label="Error rate"
          value={formatPercent(t.error_rate, 2)}
          sub={`${formatNumber(t.errors)} failed`}
          tone={t.error_rate > 0.01 ? "bad" : "good"}
        />
        <Kpi
          icon={<Hash size={15} />}
          label="Tokens"
          value={formatNumber(t.tokens_input + t.tokens_output)}
          sub={`${formatNumber(t.tokens_input)} in · ${formatNumber(t.tokens_output)} out`}
        />
        <Kpi
          icon={<Coins size={15} />}
          label="Cost per request"
          value={formatUsd(t.estimated_cost_per_request_usd)}
          sub={`${formatUsd(t.estimated_cost_usd)} total, estimated`}
        />
      </section>

      {d.series.length > 1 && (
        <section className="grid gap-3 md:grid-cols-2">
          <Card title="p95 latency" subtitle="End to end, per hour">
            <TimeSeriesChart points={points("p95_latency_ms")} format={formatMs} label="p95 latency by hour" />
          </Card>
          <Card title="Request volume" subtitle="Requests per hour">
            <TimeSeriesChart
              points={points("requests")}
              format={(v) => formatNumber(Math.round(v))}
              kind="bar"
              label="Requests per hour"
            />
          </Card>
          <Card title="Cache hit rate" subtitle="Share of cache lookups that hit">
            <TimeSeriesChart points={points("cache_hit_rate")} format={(v) => formatPercent(v)} label="Cache hit rate by hour" />
          </Card>
          <Card title="Error rate" subtitle="Failed requests as a share of total">
            <TimeSeriesChart points={points("error_rate")} format={(v) => formatPercent(v, 2)} label="Error rate by hour" />
          </Card>
        </section>
      )}

      <section className="grid gap-3 lg:grid-cols-5">
        <Card
          className="lg:col-span-3"
          title="Where the time goes"
          subtitle={stageSubtitle(d)}
          icon={<Gauge size={15} />}
        >
          {d.stages.length === 0 ? (
            <Empty>No timed requests in this window yet.</Empty>
          ) : (
            <>
              <ul className="space-y-3">
                {d.stages.map((s) => (
                  <li key={s.stage}>
                    <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                      <span className="capitalize">{s.stage}</span>
                      <span className="font-mono text-xs tabular-nums text-muted">
                        p50 {formatMs(s.p50_ms)} · p95 {formatMs(s.p95_ms)}
                      </span>
                    </div>
                    <Meter value={s.p50_ms} secondary={s.p95_ms} max={maxStage} />
                  </li>
                ))}
              </ul>
              <Legend items={[["Solid", "p50"], ["Faded", "p95"]]} />
            </>
          )}
        </Card>

        <Card className="lg:col-span-2" title="Caches" subtitle="Paid calls avoided" icon={<Layers size={15} />}>
          {d.cache_layers.every((c) => c.lookups === 0) ? (
            <Empty>Nothing has been looked up yet.</Empty>
          ) : (
            <ul className="space-y-4">
              {d.cache_layers.map((c) => (
                <li key={c.layer}>
                  <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                    <span>{c.layer}</span>
                    <span className="font-mono text-xs tabular-nums text-muted">
                      {c.lookups ? formatPercent(c.hit_rate) : "—"}
                    </span>
                  </div>
                  <Meter value={c.hit_rate} tone="good" />
                  <p className="mt-1 text-xs text-subtle">
                    {formatNumber(c.saved_calls)} of {formatNumber(c.lookups)} · {c.meaning}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        <Card title="Corpus and retrieval" subtitle="What the answers are grounded in" icon={<Database size={15} />}>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
            <Stat label="Documents" value={formatNumber(d.corpus.documents)} />
            <Stat label="Pages" value={formatNumber(d.corpus.pages)} />
            <Stat
              label="Chunks embedded"
              value={`${formatNumber(d.corpus.embedded_chunks)} of ${formatNumber(d.corpus.chunks)}`}
            />
            <Stat label="Passages per answer" value={String(d.corpus.retrieve_k)} />
            <Stat label="Search" value={d.corpus.index} wide />
            <Stat
              label="Embeddings"
              value={`${d.corpus.embedding_model} · ${d.corpus.embedding_dim} dimensions`}
              wide
            />
            <Stat label="Generation" value={d.corpus.llm_model} wide />
          </dl>
        </Card>

        <Card title="Slowest queries" subtitle="Worst latency in this window" icon={<Clock size={15} />}>
          {d.slowest.length === 0 ? (
            <Empty>No queries in this window yet.</Empty>
          ) : (
            <ol className="space-y-2.5">
              {d.slowest.map((s, i) => (
                <li key={`${s.at}-${i}`} className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="min-w-0 flex-1 truncate" title={s.query}>
                    {s.query}
                  </span>
                  {s.cache_hit && <Zap size={12} className="shrink-0 text-good" aria-label="served from cache" />}
                  <span className="shrink-0 font-mono text-xs tabular-nums text-muted">{formatMs(s.latency_ms)}</span>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </section>
    </>
  );
}

/** Hits over lookups across every cache, not an average of the two rates. */
function overallHitRate(d: Analytics): number {
  const lookups = d.cache_layers.reduce((sum, c) => sum + c.lookups, 0);
  return lookups ? savedCalls(d) / lookups : 0;
}

function savedCalls(d: Analytics): number {
  return d.cache_layers.reduce((sum, c) => sum + c.saved_calls, 0);
}

function stageSubtitle(d: Analytics): string {
  const total = d.stages.reduce((sum, s) => sum + s.p50_ms, 0);
  const slowest = d.stages[0];
  if (!slowest || !total) return "Median and 95th percentile per stage";
  return `${slowest.stage} is ${formatPercent(slowest.p50_ms / total, 0)} of median latency`;
}

function Kpi({
  icon,
  label,
  value,
  sub,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  sub: string;
  tone?: "good" | "bad";
}) {
  return (
    <div className="rounded-xl border border-line bg-elevated p-4">
      <div className="flex items-center gap-1.5 text-xs text-muted">
        <span className={tone === "good" ? "text-good" : tone === "bad" ? "text-bad" : "text-subtle"}>{icon}</span>
        {label}
      </div>
      <div className="mt-2 font-mono text-xl font-semibold tabular-nums tracking-tight">{value}</div>
      <div className="mt-1 truncate text-xs text-subtle">{sub}</div>
    </div>
  );
}

function Card({
  title,
  subtitle,
  icon,
  className = "",
  children,
}: {
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`rounded-xl border border-line bg-elevated p-4 sm:p-5 ${className}`}>
      <header className="mb-4">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold">
          {icon && <span className="text-subtle">{icon}</span>}
          {title}
        </h3>
        {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}

function Stat({ label, value, wide }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? "col-span-2" : ""}>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5 break-words font-medium">{value}</dd>
    </div>
  );
}

function Legend({ items }: { items: [string, string][] }) {
  return (
    <p className="mt-4 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-subtle">
      {items.map(([key, meaning]) => (
        <span key={key}>
          <span className="font-medium text-muted">{key}</span> {meaning}
        </span>
      ))}
    </p>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="py-2 text-sm text-subtle">{children}</p>;
}

/** A window with no traffic is normal on a personal deployment, not an error. */
function EmptyWindow() {
  return (
    <div className="rounded-xl border border-line bg-elevated p-8 text-center">
      <p className="text-sm font-medium">No requests in this window</p>
      <p className="mt-1 text-sm text-muted">
        Ask something in the chat and the numbers here will be measured from it.
      </p>
      <Link
        href="/"
        className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-accent-fg"
      >
        Go to chat
      </Link>
    </div>
  );
}

function LoadingState() {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-24 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-52 rounded-xl" />
        ))}
      </div>
    </div>
  );
}
