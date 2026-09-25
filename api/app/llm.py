"""Write an answer from retrieved passages, and tie each claim to its source.

The model is not asked to know EU law. The passages carry the knowledge; the
model's job is to put them into a sentence and say which one it used. That is
why the cheapest tier is enough, and why the prompt below spends most of its
words forbidding the model from answering out of memory.

An ungrounded answer is the worst failure this system can have: a confident
citation to an article that does not say what the answer claims. "The sources
do not cover this" is a correct answer, and the prompt says so explicitly.
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
    text: str
    citations: list[Citation]
    tokens_input: int
    tokens_output: int
    # Passages put in front of the model, which is more than the number cited:
    # the difference is how much of the retrieval the answer actually used.
    retrieved: int = 0


def build_llm() -> ChatGoogleGenerativeAI:
    """Built once at startup; constructing it per request would add latency."""
    if not settings.google_api_key:
        raise RuntimeError("Set GOOGLE_API_KEY to generate answers")
    extra = {}
    # Only sent when set: this model rejects thinking_budget=0 with a 400, so
    # "leave it alone" has to mean not sending the argument at all.
    if settings.llm_thinking_budget is not None:
        extra["thinking_budget"] = settings.llm_thinking_budget
    return ChatGoogleGenerativeAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        google_api_key=settings.google_api_key,
        **extra,
    )


def format_sources(chunks: list[dict]) -> str:
    """Number the passages so the model has something to cite.

    The title and page travel with each one because the model writes better
    attributions when it can see what it is citing.
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
    """Every source number the answer refers to, in order of first appearance."""
    seen: list[int] = []
    for match in CITATION.finditer(text):
        for part in match.group(1).split(","):
            number = int(part.strip())
            if number not in seen:
                seen.append(number)
    return seen


def collect_citations(text: str, chunks: list[dict]) -> list[Citation]:
    """Resolve the numbers in an answer back to the passages they point at.

    Numbers outside the range are dropped rather than trusted: a model that
    invents [9] from six sources has invented the claim attached to it, and a
    citation that resolves to nothing would break the viewer.
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
    """The answer as a string.

    Newer models return a list of typed blocks rather than plain text, and
    reasoning blocks travel alongside the answer. Only the text blocks are the
    answer; str() on the list would put its Python repr in front of the user.
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
    """Real token counts from the response, for cost and metrics.

    Reported by the API rather than estimated from word counts: an estimate
    would make every cost number in the report fiction.
    """
    meta = getattr(response, "usage_metadata", None) or {}
    return int(meta.get("input_tokens", 0)), int(meta.get("output_tokens", 0))


@traceable(run_type="chain", name="answer_question")
async def answer_question(llm: ChatGoogleGenerativeAI, query: str, chunks: list[dict]) -> Answer:
    """Turn a question and its retrieved passages into a cited answer.

    Traced as the parent of the model call, so one trace carries the question,
    the passages it was given, the answer, and the tokens it cost.
    """
    if not chunks:
        # Nothing retrieved means nothing to ground an answer in, so there is
        # no reason to spend a call to find that out.
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
