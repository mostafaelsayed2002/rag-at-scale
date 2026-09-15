import type { DocumentContent } from "../types";

/**
 * Mock corpus. Passages are short paraphrases of the real provisions, not
 * official text, and page numbers are approximate. Replaced by GET /documents
 * and GET /documents/:id once the backend serves the real corpus.
 */
export const MOCK_DOCUMENTS: DocumentContent[] = [
  {
    id: "gdpr",
    title: "General Data Protection Regulation",
    shortTitle: "GDPR",
    format: "pdf",
    collection: "Legislation",
    identifier: "Regulation (EU) 2016/679",
    publishedAt: "2016-04-27",
    pageCount: 88,
    chunkCount: 412,
    sourceUrl: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679",
    sections: [
      {
        id: "art-5",
        heading: "Article 5 · Principles relating to processing",
        page: 35,
        paragraphs: [
          "Personal data must be processed lawfully, fairly and transparently, collected for specified and legitimate purposes, and limited to what is necessary for those purposes.",
          "Data must be accurate, kept no longer than necessary, and protected with appropriate security. The controller is responsible for, and must be able to demonstrate, compliance with these principles.",
        ],
      },
      {
        id: "art-6",
        heading: "Article 6 · Lawfulness of processing",
        page: 36,
        paragraphs: [
          "Processing is lawful only where at least one legal basis applies: consent, performance of a contract, a legal obligation, vital interests, a task in the public interest, or legitimate interests not overridden by the rights of the data subject.",
        ],
      },
      {
        id: "art-17",
        heading: "Article 17 · Right to erasure",
        page: 43,
        paragraphs: [
          "The data subject can require the controller to erase their personal data without undue delay where, among other grounds, the data is no longer necessary, consent is withdrawn, the person objects, or the processing was unlawful.",
          "The right does not apply where processing is necessary for freedom of expression, compliance with a legal obligation, public health, archiving in the public interest, or the establishment or defence of legal claims.",
        ],
      },
      {
        id: "art-33",
        heading: "Article 33 · Notification of a personal data breach",
        page: 52,
        paragraphs: [
          "The controller must notify the competent supervisory authority without undue delay and, where feasible, within 72 hours of becoming aware of a breach, unless the breach is unlikely to result in a risk to people's rights and freedoms.",
          "A notification made after 72 hours must explain the reasons for the delay. It must describe the breach, the likely consequences, and the measures taken or proposed.",
        ],
      },
      {
        id: "art-34",
        heading: "Article 34 · Communication of a breach to the data subject",
        page: 53,
        paragraphs: [
          "Where a breach is likely to result in a high risk, the controller must also inform the affected individuals without undue delay, in clear and plain language.",
        ],
      },
      {
        id: "art-83",
        heading: "Article 83 · Administrative fines",
        page: 82,
        paragraphs: [
          "Fines must be effective, proportionate and dissuasive. Infringements of obligations such as security and breach notification can reach 10 million euro or 2% of worldwide annual turnover, whichever is higher.",
          "Infringements of the core principles, legal bases and data subject rights can reach 20 million euro or 4% of worldwide annual turnover, whichever is higher.",
        ],
      },
    ],
  },
  {
    id: "ai-act",
    title: "Artificial Intelligence Act",
    shortTitle: "AI Act",
    format: "pdf",
    collection: "Legislation",
    identifier: "Regulation (EU) 2024/1689",
    publishedAt: "2024-06-13",
    pageCount: 144,
    chunkCount: 689,
    sourceUrl: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689",
    sections: [
      {
        id: "art-5",
        heading: "Article 5 · Prohibited AI practices",
        page: 51,
        paragraphs: [
          "Certain practices are banned outright, including manipulative or deceptive techniques that materially distort behaviour, exploiting vulnerabilities due to age or disability, and social scoring that leads to unjustified detrimental treatment.",
          "Also prohibited are untargeted scraping of facial images to build recognition databases, emotion recognition in workplaces and education except for medical or safety reasons, and biometric categorisation to infer sensitive characteristics.",
        ],
      },
      {
        id: "art-6",
        heading: "Article 6 · Classification rules for high-risk AI systems",
        page: 53,
        paragraphs: [
          "An AI system is high-risk where it is a safety component of a product covered by the Union harmonisation legislation in Annex I, or where it falls within one of the use cases listed in Annex III.",
          "A system listed in Annex III is not high-risk if it does not pose a significant risk of harm, for instance because it only performs a narrow procedural task. The provider must document that assessment.",
        ],
      },
      {
        id: "art-50",
        heading: "Article 50 · Transparency obligations",
        page: 82,
        paragraphs: [
          "Providers must ensure people are informed when they interact with an AI system, unless that is obvious from the context. Synthetic audio, image, video and text content must be marked in a machine-readable format as artificially generated.",
          "Deployers of systems that generate deep fakes must disclose that the content has been artificially generated or manipulated.",
        ],
      },
      {
        id: "art-99",
        heading: "Article 99 · Penalties",
        page: 112,
        paragraphs: [
          "Non-compliance with the prohibited practices in Article 5 can lead to fines of up to 35 million euro or 7% of worldwide annual turnover, whichever is higher.",
          "Breaches of most other obligations can reach 15 million euro or 3%, and supplying incorrect or misleading information to authorities can reach 7.5 million euro or 1%.",
        ],
      },
      {
        id: "art-113",
        heading: "Article 113 · Entry into force and application",
        page: 123,
        paragraphs: [
          "The Regulation applies generally from 2 August 2026. The prohibitions and AI literacy provisions apply from 2 February 2025, and the obligations for general-purpose AI models from 2 August 2025.",
          "The classification rule for high-risk systems embedded in products under Annex I applies from 2 August 2027.",
        ],
      },
      {
        id: "annex-3",
        heading: "Annex III · High-risk AI systems",
        page: 127,
        paragraphs: [
          "Employment and workers management: AI systems intended for recruitment or selection, in particular to place targeted job advertisements, analyse and filter applications, and evaluate candidates.",
          "Also listed: systems used to make decisions on promotion or termination, allocate tasks based on individual behaviour or traits, and monitor or evaluate the performance and behaviour of workers.",
        ],
      },
    ],
  },
  {
    id: "data-act",
    title: "Data Act",
    shortTitle: "Data Act",
    format: "pdf",
    collection: "Legislation",
    identifier: "Regulation (EU) 2023/2854",
    publishedAt: "2023-12-13",
    pageCount: 71,
    chunkCount: 318,
    sourceUrl: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32023R2854",
    sections: [
      {
        id: "art-3",
        heading: "Article 3 · Making product data accessible to the user",
        page: 26,
        paragraphs: [
          "Connected products must be designed so that the data they generate is, by default, easily and securely accessible to the user, directly where relevant and technically feasible.",
        ],
      },
      {
        id: "art-4",
        heading: "Article 4 · Rights of users to access and use data",
        page: 27,
        paragraphs: [
          "Where data cannot be accessed directly, the data holder must make it available to the user without undue delay, free of charge, and where applicable continuously and in real time.",
        ],
      },
      {
        id: "art-23",
        heading: "Article 23 · Switching between data processing services",
        page: 45,
        paragraphs: [
          "Providers of cloud and other data processing services must remove obstacles that prevent customers from switching to another provider or porting their data and digital assets.",
        ],
      },
    ],
  },
  {
    id: "dga",
    title: "Data Governance Act",
    shortTitle: "DGA",
    format: "pdf",
    collection: "Legislation",
    identifier: "Regulation (EU) 2022/868",
    publishedAt: "2022-05-30",
    pageCount: 44,
    chunkCount: 196,
    sourceUrl: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R0868",
    sections: [
      {
        id: "art-10",
        heading: "Article 10 · Data intermediation services",
        page: 19,
        paragraphs: [
          "Services that intermediate between data holders and data users are subject to a notification procedure and must remain neutral with respect to the data they exchange.",
        ],
      },
      {
        id: "art-16",
        heading: "Article 16 · Data altruism",
        page: 24,
        paragraphs: [
          "Member States may put in place arrangements to facilitate data altruism, the voluntary sharing of data for objectives of general interest such as healthcare or scientific research.",
        ],
      },
    ],
  },
  {
    id: "nis2",
    title: "NIS2 Directive",
    shortTitle: "NIS2",
    format: "pdf",
    collection: "Legislation",
    identifier: "Directive (EU) 2022/2555",
    publishedAt: "2022-12-14",
    pageCount: 80,
    chunkCount: 361,
    sourceUrl: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022L2555",
    sections: [
      {
        id: "art-21",
        heading: "Article 21 · Cybersecurity risk-management measures",
        page: 48,
        paragraphs: [
          "Essential and important entities must take appropriate technical, operational and organisational measures, including policies on risk analysis, incident handling, business continuity, supply chain security, and the use of cryptography.",
        ],
      },
      {
        id: "art-23",
        heading: "Article 23 · Reporting obligations",
        page: 50,
        paragraphs: [
          "Significant incidents must be reported in stages: an early warning within 24 hours of becoming aware, an incident notification within 72 hours, and a final report within one month.",
        ],
      },
    ],
  },
  {
    id: "dsa",
    title: "Digital Services Act",
    shortTitle: "DSA",
    format: "pdf",
    collection: "Legislation",
    identifier: "Regulation (EU) 2022/2065",
    publishedAt: "2022-10-19",
    pageCount: 102,
    chunkCount: 447,
    sourceUrl: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32022R2065",
    sections: [
      {
        id: "art-16",
        heading: "Article 16 · Notice and action mechanisms",
        page: 51,
        paragraphs: [
          "Hosting services must put in place easy to access, user-friendly mechanisms that allow anyone to notify them of content they consider to be illegal.",
        ],
      },
      {
        id: "art-34",
        heading: "Article 34 · Risk assessment",
        page: 64,
        paragraphs: [
          "Very large online platforms and search engines must identify, analyse and assess systemic risks stemming from their services, including the dissemination of illegal content and negative effects on fundamental rights.",
        ],
      },
    ],
  },
  {
    id: "edpb-ai-models",
    title: "Opinion 28/2024 on data protection aspects of AI models",
    shortTitle: "EDPB Opinion 28/2024",
    format: "pdf",
    collection: "EDPB",
    identifier: "Opinion 28/2024",
    publishedAt: "2024-12-17",
    pageCount: 36,
    chunkCount: 142,
    sourceUrl: "https://www.edpb.europa.eu/",
    sections: [
      {
        id: "anonymity",
        heading: "3.1 · When an AI model can be considered anonymous",
        page: 13,
        paragraphs: [
          "Whether a model trained on personal data is anonymous has to be assessed case by case. The likelihood of extracting personal data from the model, directly or through queries, must be insignificant.",
        ],
      },
      {
        id: "legitimate-interest",
        heading: "3.2 · Legitimate interest as a legal basis",
        page: 18,
        paragraphs: [
          "Controllers relying on legitimate interest must apply the three-step test: identify a legitimate interest, show the processing is necessary for it, and balance it against the interests and rights of the people concerned.",
        ],
      },
    ],
  },
  {
    id: "edpb-breach-examples",
    title: "Guidelines 01/2021 on examples regarding personal data breach notification",
    shortTitle: "EDPB Guidelines 01/2021",
    format: "pdf",
    collection: "EDPB",
    identifier: "Guidelines 01/2021",
    publishedAt: "2022-01-03",
    pageCount: 33,
    chunkCount: 128,
    sourceUrl: "https://www.edpb.europa.eu/",
    sections: [
      {
        id: "ransomware",
        heading: "2 · Ransomware",
        page: 7,
        paragraphs: [
          "Where encrypted data is restored from a backup and there is no evidence of exfiltration, the breach may not need to be notified, but it must still be documented in the internal breach register.",
        ],
      },
      {
        id: "awareness",
        heading: "1.2 · When a controller becomes aware",
        page: 5,
        paragraphs: [
          "A controller becomes aware of a breach once it has a reasonable degree of certainty that a security incident has compromised personal data. The 72-hour period starts from that moment.",
        ],
      },
    ],
  },
  {
    id: "ai-act-prohibited-guidelines",
    title: "Commission Guidelines on prohibited AI practices",
    shortTitle: "Prohibited practices guidelines",
    format: "pdf",
    collection: "AI Office",
    identifier: "C(2025) 884",
    publishedAt: "2025-02-04",
    pageCount: 140,
    chunkCount: 604,
    sourceUrl: "https://digital-strategy.ec.europa.eu/",
    sections: [
      {
        id: "emotion-recognition",
        heading: "8 · Emotion recognition in the workplace and education",
        page: 92,
        paragraphs: [
          "The prohibition covers systems that infer emotions of employees or students from biometric data. Detecting physical states such as fatigue for safety purposes, or medical uses, fall outside the ban.",
        ],
      },
    ],
  },
  {
    id: "gpai-code",
    title: "General-Purpose AI Code of Practice",
    shortTitle: "GPAI Code of Practice",
    format: "pdf",
    collection: "AI Office",
    identifier: "GPAI CoP 2025",
    publishedAt: "2025-07-10",
    pageCount: 58,
    chunkCount: 231,
    sourceUrl: "https://digital-strategy.ec.europa.eu/",
    sections: [
      {
        id: "chapters",
        heading: "Structure of the Code",
        page: 3,
        paragraphs: [
          "The Code is organised in three chapters: transparency, copyright, and safety and security. The safety and security chapter applies only to providers of models with systemic risk.",
        ],
      },
      {
        id: "transparency",
        heading: "Transparency chapter · Model documentation",
        page: 9,
        paragraphs: [
          "Signatories keep up-to-date documentation of their models and provide relevant information to downstream providers who integrate the model into their own AI systems.",
        ],
      },
    ],
  },
  {
    id: "enisa-etl-2024",
    title: "ENISA Threat Landscape 2024",
    shortTitle: "ENISA Threat Landscape 2024",
    format: "pdf",
    collection: "ENISA",
    identifier: "ENISA ETL 2024",
    publishedAt: "2024-09-19",
    pageCount: 124,
    chunkCount: 488,
    sourceUrl: "https://www.enisa.europa.eu/",
    sections: [
      {
        id: "prime-threats",
        heading: "Prime threats",
        page: 8,
        paragraphs: [
          "Threats against availability, ransomware and threats against data remain at the top of the landscape, with a growing share of incidents linked to geopolitical tensions.",
        ],
      },
    ],
  },
  {
    id: "ai-act-timeline",
    title: "AI Act implementation timeline",
    shortTitle: "AI Act timeline",
    format: "md",
    collection: "Notes",
    identifier: "notes/ai-act-timeline.md",
    publishedAt: "2025-08-04",
    pageCount: null,
    chunkCount: 14,
    sourceUrl: "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1689",
    sections: [
      {
        id: "milestones",
        heading: "Key milestones",
        page: null,
        paragraphs: [
          "1 August 2024: the Regulation enters into force.",
          "2 February 2025: prohibitions and AI literacy obligations apply.",
          "2 August 2025: obligations for general-purpose AI models and governance rules apply.",
          "2 August 2026: most remaining provisions apply, including high-risk systems listed in Annex III.",
          "2 August 2027: rules for high-risk systems embedded in regulated products apply.",
        ],
      },
    ],
  },
  {
    id: "glossary",
    title: "Regulatory glossary",
    shortTitle: "Glossary",
    format: "md",
    collection: "Notes",
    identifier: "notes/glossary.md",
    publishedAt: "2025-06-12",
    pageCount: null,
    chunkCount: 22,
    sourceUrl: "https://eur-lex.europa.eu/",
    sections: [
      {
        id: "controller",
        heading: "Controller",
        page: null,
        paragraphs: [
          "The organisation that determines the purposes and means of processing personal data. Most GDPR obligations fall on the controller.",
        ],
      },
      {
        id: "provider-deployer",
        heading: "Provider and deployer",
        page: null,
        paragraphs: [
          "Under the AI Act, the provider develops an AI system and places it on the market; the deployer uses it under its own authority. Obligations differ significantly between the two roles.",
        ],
      },
    ],
  },
];
