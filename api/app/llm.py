"""Write a cited answer using only the retrieved passages.

The passages hold the knowledge; the model only phrases it and cites sources,
so the cheapest model is enough. Answering from memory is the worst failure,
so "the sources do not cover this" is a valid answer.
"""

import logging
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import traceable
from pydantic import BaseModel

from .config import settings

logger = logging.getLogger(__name__)

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

# [1], or [1][2], or [1, 2] — the shapes a model actually produces.
CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


class Citation(BaseModel):
    """One source behind an answer, in the shape the PDF viewer expects."""

    n: int
    chunk_id: int
    doc_id: str
    title: str | None
    page_start: int
    page_end: int
    # The passage itself, so the viewer can find and highlight it in the PDF.
    quote: str
    score: float


class Answer(BaseModel):
    """A generated answer. This is what the cache stores."""

    text: str
    citations: list[Citation]
    tokens_input: int
    tokens_output: int
    # Passages given to the model (usually more than were cited). Stored here
    # so a cached answer can still report it.
    retrieved: int = 0


def build_llm() -> ChatGoogleGenerativeAI:
    """Create the Gemini chat client. Built once at startup and reused."""
    extra = {}
    # Only sent when set: this model rejects thinking_budget=0.
    if settings.llm_thinking_budget is not None:
        extra["thinking_budget"] = settings.llm_thinking_budget
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        google_api_key=settings.google_api_key,
        **extra,
    )


def format_sources(chunks: list[dict]) -> str:
    """Number the passages so the model can cite them.

    Example: "[1] GDPR (page 17)\n<passage text>"
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


def cited_numbers(text: str) -> list[int]:
    """Source numbers cited in the answer, without duplicates, in first-seen order.

    Example: "Erase data [1]. Exceptions [2, 1] and [3]." -> [1, 2, 3]
    """
    seen: list[int] = []
    for match in CITATION.finditer(text):
        for part in match.group(1).split(","):
            number = int(part.strip())
            if number not in seen:
                seen.append(number)
    return seen


def collect_citations(text: str, chunks: list[dict]) -> list[Citation]:
    """Turn the cited numbers into Citation objects for the UI's source cards.

    [n] points to the n-th passage. Numbers with no passage (e.g. [9] when
    there are 6) are made up by the model, so they are logged and dropped.
    """
    citations = []
    for number in cited_numbers(text):
        if not 1 <= number <= len(chunks):
            logger.warning("answer cited [%d] with only %d sources", number, len(chunks))
            continue
        chunk = chunks[number - 1]
        citations.append(
            Citation(
                n=number,
                chunk_id=chunk["chunk_id"],
                doc_id=chunk["doc_id"],
                title=chunk.get("title"),
                page_start=chunk["page_start"],
                page_end=chunk["page_end"],
                quote=chunk["text"],
                score=chunk["score"],
            )
        )
    return citations


def extract_text(content) -> str:
    """Get the answer text from the model response.

    Newer models return a list of blocks (text plus reasoning); only the
    text blocks are the answer.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block["text"]
            for block in content
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
        ]
        return "\n".join(parts)
    return str(content)


def usage(response) -> tuple[int, int]:
    """(input, output) token counts reported by Gemini; 0 if missing."""
    meta = getattr(response, "usage_metadata", None) or {}
    return int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))


@traceable(run_type="chain", name="answer_question")
async def answer_question(llm: ChatGoogleGenerativeAI, query: str, chunks: list[dict]) -> Answer:
    """Ask the model to answer from the passages, and return a cited Answer.

    Traced in LangSmith with the question, passages, answer and tokens.
    """
    if not chunks:
        # No passages, nothing to ground an answer in: skip the model call.
        return Answer(
            text="I could not find anything about that in the corpus.",
            citations=[],
            tokens_input=0,
            tokens_output=0,
        )

    prompt = f"{SYSTEM_PROMPT}\n\nSources:\n\n{format_sources(chunks)}\n\nQuestion: {query}"
    response = await llm.ainvoke(prompt)
    text = extract_text(response.content)
    tokens_input, tokens_output = usage(response)

    return Answer(
        text=text.strip(),
        citations=collect_citations(text, chunks),
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        retrieved=len(chunks),
    )
