"""The prompt sent to the model, and how the passages are laid out in it."""

SYSTEM_PROMPT = """You answer questions about EU AI and data regulation.

Rules:
- Use ONLY the numbered sources below. Never use knowledge from your training,
  even if you are certain it is correct.
- Mark every factual claim with the source it came from, like [1] or [2][3].
- If the sources do not answer the question, say exactly that and stop. Do not
  fill the gap from memory. An honest "the sources provided do not cover this"
  is a correct and useful answer.
- Do not invent source numbers. Only cite numbers that appear below.
- Quote regulation wording exactly when precision matters; paraphrase otherwise.
- Be concise: a few sentences, unless the question genuinely needs more.
"""


def format_sources(chunks: list[dict]) -> str:
    """Number the passages so the model can cite them.

    Example: "[1] GDPR (page 17)\\n<passage text>"
    """
    blocks = []
    for n, chunk in enumerate(chunks, start=1):
        title = chunk.get("title") or chunk["doc_id"]
        pages = (
            f"page {chunk['page_start']}"
            if chunk["page_start"] == chunk["page_end"]
            else f"pages {chunk['page_start']}-{chunk['page_end']}"
        )
        blocks.append(f"[{n}] {title} ({pages})\n{chunk['text']}")
    return "\n\n".join(blocks)


def build_prompt(query: str, chunks: list[dict]) -> str:
    return f"{SYSTEM_PROMPT}\n\nSources:\n\n{format_sources(chunks)}\n\nQuestion: {query}"
