"""Write a cited answer using only the retrieved passages.

The passages hold the knowledge; the model only phrases it and cites sources,
so the cheapest model is enough. Answering from memory is the worst failure,
so "the sources do not cover this" is a valid answer.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import traceable

from ..core.config import settings
from ..core.errors import QuotaExhausted, is_quota_error
from .citations import collect_citations
from .prompts import build_prompt
from .types import Answer


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

    try:
        response = await llm.ainvoke(build_prompt(query, chunks))
    except Exception as exc:
        if is_quota_error(exc):
            raise QuotaExhausted("generation", str(exc)) from exc
        raise
    text = extract_text(response.content)
    tokens_input, tokens_output = usage(response)

    return Answer(
        text=text.strip(),
        citations=collect_citations(text, chunks),
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        retrieved=len(chunks),
    )
