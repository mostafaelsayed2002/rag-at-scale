"""Write a cited answer using only the retrieved passages.

The passages hold the knowledge; the model only phrases it and cites sources,
so the cheapest model is enough. Answering from memory is the worst failure,
so "the sources do not cover this" is a valid answer.
"""

from collections.abc import AsyncIterator

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


def final_answer(outputs: list) -> dict:
    """What LangSmith keeps of a streamed answer: the finished Answer, not every piece."""
    answers = [item for item in outputs if isinstance(item, Answer)]
    return answers[-1].model_dump() if answers else {}


@traceable(run_type="chain", name="answer_question", reduce_fn=final_answer)
async def stream_answer(
    llm: ChatGoogleGenerativeAI, query: str, chunks: list[dict]
) -> AsyncIterator[str | Answer]:
    """Ask the model to answer from the passages. Yields the text in pieces as
    the model writes it, then the finished, cited Answer.

    Citations are read from the [n] markers, so they come with the finished
    Answer: only the whole text has all of them.
    Traced in LangSmith with the question, passages, answer and tokens.
    """
    if not chunks:
        # No passages, nothing to ground an answer in: skip the model call.
        yield Answer(
            text="I could not find anything about that in the corpus.",
            citations=[],
            tokens_input=0,
            tokens_output=0,
        )
        return

    pieces = []
    whole = None  # the chunks added up: the last ones carry the token counts
    try:
        async for chunk in llm.astream(build_prompt(query, chunks)):
            whole = chunk if whole is None else whole + chunk
            piece = extract_text(chunk.content)
            if piece:
                pieces.append(piece)
                yield piece
    except Exception as exc:
        if is_quota_error(exc):
            raise QuotaExhausted("generation", str(exc)) from exc
        raise
    text = "".join(pieces)
    tokens_input, tokens_output = usage(whole)

    yield Answer(
        text=text.strip(),
        citations=collect_citations(text, chunks),
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        retrieved=len(chunks),
    )


async def answer_question(llm: ChatGoogleGenerativeAI, query: str, chunks: list[dict]) -> Answer:
    """The whole cited Answer at once (the non-streaming /chat and the eval)."""
    async for item in stream_answer(llm, query, chunks):
        if isinstance(item, Answer):
            return item
    raise RuntimeError("the answer stream ended without an answer")
