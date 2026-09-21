"use client";

import { ArrowUpRight } from "lucide-react";
import { DemoBadge } from "../ui";

const EXAMPLES = [
  { title: "Breach notification", question: "How quickly must we report a data breach?" },
  { title: "High-risk AI", question: "Is our CV screening tool regulated under the AI Act?" },
  { title: "Right to erasure", question: "A customer wants all their data deleted. Do we have to?" },
  { title: "Prohibited practices", question: "Which AI practices are prohibited in the EU?" },
  { title: "NIS2 reporting", question: "What are the NIS2 incident reporting deadlines?" },
  { title: "Fines", question: "What is the maximum fine under the GDPR and the AI Act?" },
];

export function EmptyState({ onPick }: { onPick: (question: string) => void }) {
  return (
    // my-auto rather than justify-center: centring with justify-center pushes
    // overflowing content above the scroll origin, where it can't be reached.
    <div className="mx-auto my-auto w-full max-w-3xl px-4 py-10 sm:px-6">
      <div className="mb-4 sm:hidden">
        <DemoBadge />
      </div>
      <h1 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
        Ask anything about EU AI and data regulation
      </h1>
      <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-muted">
        Answers are grounded in the AI Act, GDPR, Data Act, NIS2 and guidance from the EDPB, the AI Office and ENISA.
        Every claim links to the passage it came from.
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
