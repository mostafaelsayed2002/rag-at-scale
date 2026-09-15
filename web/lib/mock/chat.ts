import type { ChatEvent, Citation, MessageMetrics } from "../types";
import { MOCK_DOCUMENTS } from "./documents";

type Source = { documentId: string; sectionId: string; score: number };
type Script = { keywords: string[]; answer: string; sources: Source[] };

/**
 * Scripted answers keyed by topic. The backend replaces this with retrieval,
 * reranking and generation; the event sequence stays identical.
 */
const SCRIPTS: Script[] = [
  {
    keywords: ["breach", "72", "notify", "notification", "report a data"],
    answer:
      "Under the GDPR, a controller must notify the competent **supervisory authority without undue delay and, where feasible, within 72 hours** of becoming aware of a personal data breach [1]. Notification can be skipped only when the breach is unlikely to result in a risk to people's rights and freedoms.\n\nThe clock starts when you have a reasonable degree of certainty that personal data has been compromised, not when the incident first occurs [2]. If you notify late, you must explain the delay [1].\n\nWhere the breach is likely to result in a **high risk**, you must also inform the affected individuals directly, in plain language [3].",
    sources: [
      { documentId: "gdpr", sectionId: "art-33", score: 0.94 },
      { documentId: "edpb-breach-examples", sectionId: "awareness", score: 0.88 },
      { documentId: "gdpr", sectionId: "art-34", score: 0.81 },
    ],
  },
  {
    keywords: ["delete", "erasure", "erase", "forgotten", "remove my data"],
    answer:
      "Yes, in most cases. The **right to erasure** lets a person require you to delete their personal data without undue delay when, for example, the data is no longer needed, they withdraw consent, or it was processed unlawfully [1].\n\nThe right is not absolute. You may keep data where processing is necessary to:\n\n- comply with a legal obligation\n- exercise freedom of expression\n- establish or defend legal claims\n\nThose exceptions are listed in the same article [1]. Whatever you decide, the processing still has to rest on a valid legal basis [2].",
    sources: [
      { documentId: "gdpr", sectionId: "art-17", score: 0.95 },
      { documentId: "gdpr", sectionId: "art-6", score: 0.72 },
    ],
  },
  {
    keywords: ["cv", "recruit", "hiring", "candidate", "screening", "high-risk", "high risk", "employment"],
    answer:
      "Very likely yes. The AI Act lists **employment and workers management** as a high-risk area, explicitly including systems that analyse and filter job applications or evaluate candidates [1].\n\nA system in an Annex III area is high-risk unless it poses no significant risk of harm, for instance because it only performs a narrow procedural task, and the provider must document that assessment [2].\n\nIf the tool infers candidates' emotions from video or voice, it may instead fall under the **prohibition** on emotion recognition in the workplace [3]. For high-risk systems in Annex III, most obligations apply from **2 August 2026** [4].",
    sources: [
      { documentId: "ai-act", sectionId: "annex-3", score: 0.93 },
      { documentId: "ai-act", sectionId: "art-6", score: 0.86 },
      { documentId: "ai-act-prohibited-guidelines", sectionId: "emotion-recognition", score: 0.74 },
      { documentId: "ai-act-timeline", sectionId: "milestones", score: 0.69 },
    ],
  },
  {
    keywords: ["fine", "penalt", "sanction", "maximum"],
    answer:
      "It depends on the regulation and the infringement.\n\n**GDPR.** The higher tier reaches **20 million euro or 4% of worldwide annual turnover**, whichever is higher, for breaches of core principles and data subject rights. Lower-tier obligations such as breach notification reach 10 million euro or 2% [1].\n\n**AI Act.** Using a prohibited AI practice can cost up to **35 million euro or 7%** of worldwide turnover. Most other obligations reach 15 million euro or 3% [2].",
    sources: [
      { documentId: "gdpr", sectionId: "art-83", score: 0.92 },
      { documentId: "ai-act", sectionId: "art-99", score: 0.9 },
    ],
  },
  {
    keywords: ["prohibit", "banned", "forbidden", "not allowed", "social scoring"],
    answer:
      "The AI Act bans a short list of practices outright [1], including:\n\n- manipulative techniques that materially distort behaviour\n- exploiting vulnerabilities linked to age or disability\n- social scoring leading to unjustified detrimental treatment\n- untargeted scraping of facial images for recognition databases\n- emotion recognition in workplaces and education\n\nThe emotion recognition ban has carve-outs for medical and safety uses, such as detecting driver fatigue [2]. These prohibitions have applied since **2 February 2025** [3].",
    sources: [
      { documentId: "ai-act", sectionId: "art-5", score: 0.96 },
      { documentId: "ai-act-prohibited-guidelines", sectionId: "emotion-recognition", score: 0.84 },
      { documentId: "ai-act", sectionId: "art-113", score: 0.77 },
    ],
  },
  {
    keywords: ["nis2", "incident", "cyber", "24 hours"],
    answer:
      "NIS2 uses a **staged reporting** model for significant incidents [1]:\n\n1. an early warning within **24 hours** of becoming aware\n2. an incident notification within **72 hours**\n3. a final report within **one month**\n\nThis sits alongside the risk-management measures entities must already have in place, including incident handling and supply chain security [2]. If personal data is involved, the separate GDPR notification to the data protection authority still applies [3].",
    sources: [
      { documentId: "nis2", sectionId: "art-23", score: 0.95 },
      { documentId: "nis2", sectionId: "art-21", score: 0.83 },
      { documentId: "gdpr", sectionId: "art-33", score: 0.71 },
    ],
  },
  {
    keywords: ["gpai", "general-purpose", "general purpose", "foundation model", "code of practice", "llm"],
    answer:
      "Obligations for **general-purpose AI models** have applied since **2 August 2025** [1]. The Code of Practice gives providers a way to demonstrate compliance and is organised into three chapters: transparency, copyright, and safety and security [2].\n\nThe safety and security chapter applies only to models with systemic risk. Every signatory keeps model documentation up to date and shares relevant information with downstream providers [3].",
    sources: [
      { documentId: "ai-act-timeline", sectionId: "milestones", score: 0.89 },
      { documentId: "gpai-code", sectionId: "chapters", score: 0.91 },
      { documentId: "gpai-code", sectionId: "transparency", score: 0.82 },
    ],
  },
  {
    keywords: ["when", "timeline", "apply", "deadline", "date"],
    answer:
      "The AI Act entered into force on **1 August 2024** and applies in phases [1]:\n\n- **2 February 2025**: prohibitions and AI literacy\n- **2 August 2025**: general-purpose AI model obligations\n- **2 August 2026**: most remaining rules, including Annex III high-risk systems\n- **2 August 2027**: high-risk systems embedded in regulated products\n\nThe phased dates are set out in the final provisions of the Regulation [2].",
    sources: [
      { documentId: "ai-act-timeline", sectionId: "milestones", score: 0.93 },
      { documentId: "ai-act", sectionId: "art-113", score: 0.9 },
    ],
  },
];

const FALLBACK: Script = {
  keywords: [],
  answer:
    "This is demo data, so I can only answer a handful of scripted topics. The closest material I found is on the core data protection principles, which require processing to be lawful, fair, transparent and limited to its purpose [1], and on the legal bases that make processing lawful [2].\n\nTry asking about breach notification, the right to erasure, high-risk AI systems, fines, prohibited AI practices, NIS2 incident reporting, or general-purpose AI models.",
  sources: [
    { documentId: "gdpr", sectionId: "art-5", score: 0.58 },
    { documentId: "gdpr", sectionId: "art-6", score: 0.52 },
  ],
};

export function pickScript(query: string): Script {
  const q = query.toLowerCase();
  let best = FALLBACK;
  let bestHits = 0;
  for (const script of SCRIPTS) {
    const hits = script.keywords.filter((k) => q.includes(k)).length;
    if (hits > bestHits) {
      best = script;
      bestHits = hits;
    }
  }
  return best;
}

export function buildCitations(sources: Source[]): Citation[] {
  return sources.map((source, i) => {
    const doc = MOCK_DOCUMENTS.find((d) => d.id === source.documentId)!;
    const section = doc.sections.find((s) => s.id === source.sectionId)!;
    return {
      index: i + 1,
      documentId: doc.id,
      chunkId: `${doc.id}:${section.id}`,
      page: section.page,
      sectionId: section.id,
      // "Article 33 · Notification…" keeps "Article 33"; a bare number such as
      // "3.1 · When…" would read as noise, so it becomes "Section 3.1".
      locator: /^\d/.test(section.heading) ? `Section ${section.heading.split(" · ")[0]}` : section.heading.split(" · ")[0],
      snippet: section.paragraphs[0],
      score: source.score,
    };
  });
}

/** Deterministic metrics per query, so reloading a conversation looks stable. */
export function buildMetrics(query: string, answer: string): MessageMetrics {
  let seed = 0;
  for (let i = 0; i < query.length; i++) seed += query.charCodeAt(i);
  const cacheKinds: MessageMetrics["cacheHit"][] = ["none", "none", "embedding", "semantic", "none", "response"];
  const cacheHit = cacheKinds[seed % cacheKinds.length];
  const cached = cacheHit === "semantic" || cacheHit === "response";
  return {
    latencyMs: cached ? 180 + (seed % 90) : 1100 + (seed % 900),
    promptTokens: cached ? 0 : 1400 + (seed % 700),
    completionTokens: cached ? 0 : Math.round(answer.length / 4),
    cacheHit,
    retrievedChunks: 50,
  };
}

const sleep = (ms: number, signal?: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    });
  });

/**
 * Mimics the real stream: retrieval finishes first, so citations arrive before
 * any text, then the answer streams in small pieces.
 */
export async function* mockChatStream(query: string, signal?: AbortSignal): AsyncGenerator<ChatEvent> {
  const script = pickScript(query);
  await sleep(550, signal);
  yield { type: "citations", citations: buildCitations(script.sources) };

  const pieces = script.answer.match(/\S+\s*/g) ?? [];
  for (const piece of pieces) {
    await sleep(14 + Math.random() * 24, signal);
    yield { type: "token", text: piece };
  }
  yield { type: "done", metrics: buildMetrics(query, script.answer) };
}
