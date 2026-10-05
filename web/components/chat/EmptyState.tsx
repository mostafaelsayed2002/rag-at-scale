"use client";

import { ArrowUpRight } from "lucide-react";

// Spread across areas of EU law to show the corpus is all acts in force, not
// only digital regulation. Each has been checked to retrieve the right act.
const EXAMPLES = [
  { title: "Data protection", question: "When must a controller notify a personal data breach?" },
  { title: "Artificial intelligence", question: "What obligations do providers of high-risk AI systems have?" },
  { title: "Air travel", question: "What rights do air passengers have when a flight is cancelled?" },
  { title: "Online platforms", question: "Can an online platform show targeted advertising to minors?" },
  { title: "Pets", question: "What does my dog need to travel with me into the EU?" },
  { title: "Work", question: "What is the maximum weekly working time for workers?" },
];

export function EmptyState({ onPick }: { onPick: (question: string) => void }) {
  return (
    // my-auto rather than justify-center: centring with justify-center pushes
    // overflowing content above the scroll origin, where it can't be reached.
    <div className="mx-auto my-auto w-full max-w-3xl px-4 py-10 sm:px-6">
      <h1 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
        Ask anything about EU law
      </h1>
      <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-muted">
        Answers are grounded in 40,183 EU acts currently in force, from the GDPR and the AI Act to
        air passenger rights. Every claim links to the passage it came from, opened in the original PDF
        at the right page.
      </p>

      <div className="mt-8 grid gap-2 sm:grid-cols-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex.question}
            type="button"
            onClick={() => onPick(ex.question)}
            className="group flex items-start justify-between gap-3 rounded-xl border border-line bg-elevated px-4 py-3 text-left transition-colors hover:border-accent/40 hover:bg-accent-soft/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/60"
          >
            <span>
              <span className="block text-xs font-medium text-subtle">{ex.title}</span>
              <span className="mt-0.5 block text-sm">{ex.question}</span>
            </span>
            <ArrowUpRight
              size={16}
              aria-hidden
              className="mt-0.5 shrink-0 text-subtle transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent"
            />
          </button>
        ))}
      </div>
    </div>
  );
}
