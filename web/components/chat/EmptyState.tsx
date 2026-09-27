"use client";

import { ArrowUpRight } from "lucide-react";

// Matched to the documents ingested so far: a question about something
// outside the corpus has nothing to cite, and the answer says so.
const EXAMPLES = [
  { title: "Marking", question: "How should providers mark AI-generated content?" },
  { title: "Copyright", question: "What are the copyright obligations for model providers?" },
  { title: "Systemic risk", question: "What applies to models with systemic risk?" },
  { title: "AI system", question: "What is the definition of an AI system?" },
  { title: "Training data", question: "Do we need a public summary of training data?" },
  { title: "Watermarks", question: "Can tools that strip watermarks be distributed?" },
];

export function EmptyState({ onPick }: { onPick: (question: string) => void }) {
  return (
    // my-auto rather than justify-center: centring with justify-center pushes
    // overflowing content above the scroll origin, where it can't be reached.
    <div className="mx-auto my-auto w-full max-w-3xl px-4 py-10 sm:px-6">
      <h1 className="text-balance text-2xl font-semibold tracking-tight sm:text-3xl">
        Ask anything about EU AI and data regulation
      </h1>
      <p className="mt-2 max-w-xl text-[15px] leading-relaxed text-muted">
        Answers are grounded in the AI Office guidance and codes of practice ingested so far. Every claim
        links to the passage it came from, opened in the original PDF at the right page.
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
