"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Activity, AlertTriangle, ArrowLeft, Clock, Coins, Gauge, Hash, Layers, Target, Zap } from "lucide-react";
import { getMetrics } from "@/lib/api";
import { formatMs, formatNumber, formatPercent, formatUsd } from "@/lib/format";
import type { SystemMetrics } from "@/lib/types";
import { Badge, DemoBadge, Skeleton } from "../ui";
import { Meter, TimeSeriesChart } from "./Charts";

export function AnalyticsDashboard() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getMetrics()
      .then(setMetrics)
      .catch((e) => setError(e instanceof Error ? e.message : "Could not load metrics"));
  }, []);

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
          <DemoBadge />
        </div>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-6 sm:py-8">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Retrieval and generation health</h2>
          <p className="mt-1 text-sm text-muted">
            {metrics ? `${metrics.window} · updated ${new Date(metrics.generatedAt).toUTCString().slice(17, 22)} UTC` : "Loading…"}
          </p>
        </div>

        {error ? (
          <p className="rounded-lg border border-bad/30 bg-bad/5 p-4 text-sm text-bad">{error}</p>
        ) : !metrics ? (
          <LoadingState />
        ) : (
          <Dashboard m={metrics} />
        )}
      </main>
    </div>
  );
}

function Dashboard({ m }: { m: SystemMetrics }) {
  const t = m.totals;
  const maxStage = Math.max(...m.latencyBreakdown.map((s) => s.p95Ms));
  const generationShare =
    m.latencyBreakdown.find((s) => s.stage === "LLM generation")!.p50Ms /
    m.latencyBreakdown.reduce((sum, s) => sum + s.p50Ms, 0);

  return (
    <>
      <section aria-label="Key metrics" className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
        <Kpi icon={<Activity size={15} />} label="Queries" value={formatNumber(t.queries)} sub={`${Math.round(t.queries / 24)} per hour`} />
        <Kpi
          icon={<Clock size={15} />}
          label="p95 latency"
          value={formatMs(t.p95LatencyMs)}
          sub={`p50 ${formatMs(t.p50LatencyMs)} · p99 ${formatMs(t.p99LatencyMs)}`}
        />
        <Kpi icon={<Zap size={15} />} label="Cache hit rate" value={formatPercent(t.cacheHitRate)} sub="across all layers" tone="good" />
        <Kpi
          icon={<AlertTriangle size={15} />}
          label="Error rate"
          value={formatPercent(t.errorRate, 2)}
          sub={`${Math.round(t.queries * t.errorRate)} failed requests`}
          tone={t.errorRate > 0.01 ? "bad" : "good"}
        />
        <Kpi
          icon={<Hash size={15} />}
          label="Tokens per query"
          value={formatNumber(t.avgPromptTokens + t.avgCompletionTokens)}
          sub={`${formatNumber(t.avgPromptTokens)} in · ${formatNumber(t.avgCompletionTokens)} out`}
        />
        <Kpi icon={<Coins size={15} />} label="Cost per query" value={formatUsd(t.costPerQueryUsd)} sub={`${formatUsd(t.totalCostUsd)} total`} />
      </section>

      <section className="grid gap-3 md:grid-cols-2">
        <Card title="p95 latency" subtitle="End to end, per hour">
          <TimeSeriesChart points={m.series.p95LatencyMs} format={formatMs} label="p95 latency by hour" />
        </Card>
        <Card title="Query volume" subtitle="Requests per hour">
          <TimeSeriesChart points={m.series.queries} format={(v) => formatNumber(Math.round(v))} kind="bar" label="Queries per hour" />
        </Card>
        <Card title="Cache hit rate" subtitle="Share of queries served from any cache">
          <TimeSeriesChart points={m.series.cacheHitRate} format={(v) => formatPercent(v)} label="Cache hit rate by hour" />
        </Card>
        <Card title="Error rate" subtitle="Failed requests as a share of total">
          <TimeSeriesChart points={m.series.errorRate} format={(v) => formatPercent(v, 2)} label="Error rate by hour" />
        </Card>
      </section>

      <section className="grid gap-3 lg:grid-cols-5">
        <Card
          className="lg:col-span-3"
          title="Latency by pipeline stage"
          subtitle={`Generation accounts for ${formatPercent(generationShare, 0)} of median latency`}
          icon={<Gauge size={15} />}
        >
          <ul className="space-y-3">
            {m.latencyBreakdown.map((s) => (
              <li key={s.stage}>
                <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                  <span>{s.stage}</span>
                  <span className="font-mono text-xs tabular-nums text-muted">
                    p50 {formatMs(s.p50Ms)} · p95 {formatMs(s.p95Ms)}
                  </span>
                </div>
                <Meter value={s.p50Ms} secondary={s.p95Ms} max={maxStage} />
              </li>
            ))}
          </ul>
          <Legend items={[["Solid", "p50"], ["Faded", "p95"]]} />
        </Card>

        <Card className="lg:col-span-2" title="Cache layers" subtitle="Calls avoided in the window" icon={<Layers size={15} />}>
          <ul className="space-y-4">
            {m.cacheLayers.map((c) => (
              <li key={c.layer}>
                <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                  <span>{c.layer}</span>
                  <span className="font-mono text-xs tabular-nums text-muted">{formatPercent(c.hitRate)}</span>
                </div>
                <Meter value={c.hitRate} tone="good" />
                <p className="mt-1 text-xs text-subtle">{formatNumber(c.savedCalls)} calls saved</p>
              </li>
            ))}
          </ul>
        </Card>
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        <Card title="Answer quality" subtitle="RAGAS scores on the 200-question golden set" icon={<Target size={15} />}>
          <ul className="space-y-4">
            {m.quality.map((q) => {
              const pass = q.value >= q.target;
              return (
                <li key={q.metric}>
                  <div className="mb-1 flex items-center justify-between gap-3 text-sm">
                    <span>{q.metric}</span>
                    <span className="flex items-center gap-2">
                      <span className="font-mono text-xs tabular-nums">{q.value.toFixed(2)}</span>
                      <Badge tone={pass ? "good" : "warn"}>{pass ? "Pass" : "Below target"}</Badge>
                    </span>
                  </div>
                  <Meter value={q.value} target={q.target} tone={pass ? "good" : "warn"} />
                </li>
              );
            })}
          </ul>
          <Legend items={[["Tick", "CI gate threshold"]]} />
        </Card>

        <Card title="Retrieval index" subtitle="Approximate nearest-neighbour search" icon={<Layers size={15} />}>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-4 text-sm">
            <Stat label="Index" value={m.retrieval.indexType} wide />
            <Stat label="ef_search" value={String(m.retrieval.efSearch)} />
            <Stat label="Recall@10" value={formatPercent(m.retrieval.recallAt10)} />
            <Stat label="Corpus size" value={`${formatNumber(m.retrieval.corpusChunks)} chunks`} />
            <Stat
              label="Candidates"
              value={`${m.retrieval.avgChunksRetrieved} retrieved → ${m.retrieval.avgChunksAfterRerank} after rerank`}
              wide
            />
          </dl>
        </Card>
      </section>
    </>
  );
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
      <dd className="mt-0.5 font-medium">{value}</dd>
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
