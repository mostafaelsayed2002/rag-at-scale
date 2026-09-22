import type { Citation } from "../types";

/**
 * Canned answers for the demo, with citations taken from chunks that are
 * really in the database. Clicking one opens that PDF at that page and
 * highlights the passage, so the citation path can be tried without calling
 * the embedding API.
 *
 * Generated from the ingested corpus; regenerate after re-ingesting.
 */
export type Script = {
  keywords: string[];
  answer: string;
  citations: Citation[];
};

export const SCRIPTS: Script[] = [
  {
    "keywords": [
      "mark",
      "watermark",
      "label",
      "ai-generated",
      "synthetic",
      "deep fake",
      "transparency of ai"
    ],
    "answer": "Providers of generative AI systems are expected to mark what their systems produce so it can be recognised as artificially generated. The Code of Practice sets out how, including where in the pipeline the marking is applied [1].\n\nSignatories also undertake **not to distribute tools designed to strip those markings** [2], and detection mechanisms are acknowledged to be imperfect, so results are shared mainly with expert users who have a legitimate need [3].",
    "citations": [
      {
        "docId": "code_practice_ai_generated_content__original",
        "docTitle": "Code of Practice on Transparency of AI-generated Content (marking and labelling)",
        "page": 9,
        "quote": "Signatories are encouraged to implement richer metadata in accordance with Measure 1.3., , \nwithout including privacy-sensitive or business-sensitive information. In cases where such \ninformation is strictly necessary or inserted upon request of an end-user, i",
        "score": 0.9,
        "index": 1,
        "chunkId": 0
      },
      {
        "docId": "code_practice_ai_generated_content__original",
        "docTitle": "Code of Practice on Transparency of AI-generated Content (marking and labelling)",
        "page": 11,
        "quote": "11  \n  \nFurthermore, Signatories will neither place or make available on the market, nor promote or \nadvertise the use of tools whose purpose is to circumvent the machine-readable markings \nadded to the AI-generated or manipulated content for transparency. \nSi",
        "score": 0.9,
        "index": 2,
        "chunkId": 0
      },
      {
        "docId": "code_practice_ai_generated_content__original",
        "docTitle": "Code of Practice on Transparency of AI-generated Content (marking and labelling)",
        "page": 13,
        "quote": "regulators, law enforcement authorities, media, fact-checkers, trusted flaggers, independent \nresearchers, educational and research institutions, and civil society organisations. \nSignatories are encouraged to collaborate with relevant actors within the ecosys",
        "score": 0.9,
        "index": 3,
        "chunkId": 0
      }
    ]
  },
  {
    "keywords": [
      "copyright",
      "rightsholder",
      "text and data mining",
      "tdm",
      "crawler",
      "robots.txt"
    ],
    "answer": "Providers of general-purpose AI models must have a copyright policy and keep it current [1].\n\nThat includes respecting machine-readable rights reservations when crawling [2], and giving rightsholders a way to complain and to learn which crawlers were used [3].",
    "citations": [
      {
        "docId": "gpai_code_copyright_chapter__original",
        "docTitle": "General-Purpose AI Code of Practice — Copyright chapter",
        "page": 4,
        "quote": "related rights. \nMeasure 1.1 Draw up, keep up-to-date and implement a copyright policy \n(1) Signatories will draw up, keep up-to-date and implement a policy to comply with Union law \non copyright and related rights for all general-purpose AI models they place ",
        "score": 0.9,
        "index": 1,
        "chunkId": 0
      },
      {
        "docId": "gpai_code_copyright_chapter__original",
        "docTitle": "General-Purpose AI Code of Practice — Copyright chapter",
        "page": 5,
        "quote": "5 \ninfringing copyright and related rights on a commercial scale by courts or public \nauthorities in the European Union and the European Economic Area. For the purpose \nof compliance with this measure, a dynamic list of hyperlinks to lists of these websites \ni",
        "score": 0.9,
        "index": 2,
        "chunkId": 0
      },
      {
        "docId": "gpai_code_copyright_chapter__original",
        "docTitle": "General-Purpose AI Code of Practice — Copyright chapter",
        "page": 6,
        "quote": "6 \n(4) Signatories commit to take appropriate measures to enable affected rightsholders to obtain \ninformation about the web crawlers employed, their robots.txt features and other measures \nthat a Signatory adopts to identify and comply with rights reservation",
        "score": 0.9,
        "index": 3,
        "chunkId": 0
      }
    ]
  },
  {
    "keywords": [
      "systemic risk",
      "safety",
      "security",
      "lifecycle",
      "mitigation"
    ],
    "answer": "The Safety and Security chapter applies only to providers of general-purpose AI models **with systemic risk** [1].\n\nThose providers are expected to assess and mitigate risk continuously across the model's lifecycle rather than once before release [2].",
    "citations": [
      {
        "docId": "gpai_code_safety_security_chapter__original",
        "docTitle": "General-Purpose AI Code of Practice — Safety and Security chapter",
        "page": 3,
        "quote": "(b) Principle of Contextual Risk Assessment and Mitigation. The Signatories recognise that this \nSafety and Security Chapter (“Chapter”) is only relevant for providers of general-purpose AI \nmodels with systemic risk and not AI systems. However, the Signatorie",
        "score": 0.9,
        "index": 1,
        "chunkId": 0
      },
      {
        "docId": "gpai_scope_obligations_guidelines__original",
        "docTitle": "Guidelines on the scope of obligations for providers of general-purpose AI models",
        "page": 10,
        "quote": "7 \n      \n \no The model can generate language and its training compute is greater than 1023 \nFLOP. Therefore, the criterion from paragraph 17 indicates that the model \nshould be a general-purpose AI model. However, if the model can only \ncompetently perform a ",
        "score": 0.9,
        "index": 2,
        "chunkId": 0
      }
    ]
  },
  {
    "keywords": [
      "definition",
      "what is an ai system",
      "article 3",
      "scope of the ai act"
    ],
    "answer": "The Commission has published guidelines on what counts as an AI system under Article 3 of the AI Act [1].\n\nThe definition matters because it decides what the rest of the Act applies to, including the prohibited practices in Article 5 [2].",
    "citations": [
      {
        "docId": "guidelines_ai_system_definition__original",
        "docTitle": "Guidelines on the definition of an AI system (Article 3 AI Act)",
        "page": 2,
        "quote": "1 \n \nI. \nPurpose of the Guidelines  \n \n(1) \nRegulation (EU) 2024/1689 of the European Parliament and of the Council (‘the AI \nAct’)1 entered into force on 1 August 2024. The AI Act lays down harmonised rules for \nthe development, placing on the market, putting",
        "score": 0.9,
        "index": 1,
        "chunkId": 0
      },
      {
        "docId": "guidelines_ai_system_definition__original",
        "docTitle": "Guidelines on the definition of an AI system (Article 3 AI Act)",
        "page": 2,
        "quote": "1 \n \nI. \nPurpose of the Guidelines  \n \n(1) \nRegulation (EU) 2024/1689 of the European Parliament and of the Council (‘the AI \nAct’)1 entered into force on 1 August 2024. The AI Act lays down harmonised rules for \nthe development, placing on the market, putting",
        "score": 0.9,
        "index": 2,
        "chunkId": 0
      }
    ]
  },
  {
    "keywords": [
      "training",
      "training data",
      "summary",
      "template",
      "public summary"
    ],
    "answer": "Providers must publish a summary of the content used to train a general-purpose AI model, and the Commission provides a template and an explanatory notice for it [1].\n\nThe obligation follows from the AI Act, with Recital 107 giving further detail on what the summary should contain [2].",
    "citations": [
      {
        "docId": "gpai_training_content_explanatory_notice__original",
        "docTitle": "Explanatory notice and template for the public summary of training content of GPAI models (explanatory notice)",
        "page": 9,
        "quote": "8 \n \nAnnex  \nTemplate for the Public Summary of Training Content for \nGeneral-Purpose AI models required by Article 53 (1)(d) \nof Regulation (EU) 2024/1689 (AI Act) \nVersion of the Summary:  \n \nVersion of the summary, with link(s) to previous versions where ap",
        "score": 0.9,
        "index": 1,
        "chunkId": 0
      },
      {
        "docId": "gpai_training_content_explanatory_notice__original",
        "docTitle": "Explanatory notice and template for the public summary of training content of GPAI models (explanatory notice)",
        "page": 5,
        "quote": "content used for the model training15.  \n3. Relevant data processing aspects: this section of the Template requires disclosure of certain \ndata processing aspects that are relevant for the exercise of the rights of parties with legitimate \ninterests under Unio",
        "score": 0.9,
        "index": 2,
        "chunkId": 0
      }
    ]
  }
];

const FALLBACK: Script = {
  keywords: [],
  answer:
    "This is demo data with a handful of scripted answers. Try asking about marking AI-generated content, " +
    "copyright obligations, systemic risk, the definition of an AI system, or training-content summaries.",
  citations: [],
};

/** The script sharing the most keywords with the question. */
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
