"""The RAG pipeline: cache → embed → semantic cache → retrieve → rerank → generate.

No HTTP here. The chat routes call answer() (all at once) or stream() (the
text as it is written) and handle the request around them.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from langchain_google_genai import ChatGoogleGenerativeAI
from langsmith import get_current_run_tree, traceable
import httpx
from sentence_transformers import SentenceTransformer

from ..core.config import settings
from ..core.timing import Stopwatch
from ..services.cache import Cache
from .embedder import embed_vector, to_halfvec
from .generator import final_answer, stream_answer
from .reranker import rerank
from .retriever import retrieve
from .types import Answer


@dataclass
class ChatRun:
    """What one chat did, filled in as it runs, so a failed run can still be logged."""

    cache_hit: bool = False
    cache_level: str | None = None  # "exact" or "semantic" on a hit
    # Only a generated answer spends tokens; a cached one costs nothing.
    tokens_input: int = 0
    tokens_output: int = 0
    clock: Stopwatch = field(default_factory=Stopwatch)


class RagPipeline:
    """Holds the clients built at startup and answers questions with them."""

    def __init__(
        self,
        cache: Cache,
        embedder: SentenceTransformer,
        reranker: httpx.AsyncClient,
        llm: ChatGoogleGenerativeAI,
    ):
        self.cache = cache
        self.embedder = embedder
        self.reranker = reranker
        self.llm = llm

    # One LangSmith trace per question; embed, retrieve, rerank and answer_question nest inside.
    @traceable(
        run_type="chain",
        name="chat",
        process_inputs=lambda inputs: {"query": inputs.get("query")},
        reduce_fn=final_answer,
        metadata={
            "llm_model": settings.llm_model,
            "retrieve_k": settings.retrieve_k,
            "rerank_model": settings.rerank_model,
        },
    )
    async def stream(self, query: str, run: ChatRun) -> AsyncIterator[str | Answer]:
        """Yields the answer's text in pieces as the model writes it, then the
        finished Answer. A cached answer comes as the Answer alone."""
        # The models and k belong in the key: change any of them and the stored
        # answer is no longer the one this configuration would produce.
        scope = f"{settings.llm_model}:{settings.rerank_model}:{settings.retrieve_k}"
        fingerprint = f"{scope}:{query}"
        similarity = None
        stored = await self.cache.get(fingerprint)
        if stored is not None:
            run.cache_level = "exact"
        else:
            with run.clock("embedding"):
                vector = await embed_vector(self.embedder, query)
            if found := await self.cache.similar(scope, vector):
                stored, similarity = found
                run.cache_level = "semantic"
        run.cache_hit = stored is not None
        # Lets LangSmith filter cached answers from generated ones.
        if trace := get_current_run_tree():
            trace.add_metadata(
                {"cache_hit": run.cache_hit, "cache_level": run.cache_level, "similarity": similarity}
            )

        if stored is not None:
            yield Answer.model_validate_json(stored)
            return

        with run.clock("retrieval"):
            candidates = await retrieve(to_halfvec(vector), settings.rerank_candidates, settings.max_recitals)
        with run.clock("rerank"):
            chunks = await rerank(self.reranker, query, candidates, settings.retrieve_k)
        with run.clock("generation"):
            async for item in stream_answer(self.llm, query, chunks):
                if isinstance(item, Answer):
                    answer = item
                else:
                    yield item

        await self.cache.set(fingerprint, answer.model_dump_json())
        await self.cache.remember(scope, fingerprint, vector)
        run.tokens_input, run.tokens_output = answer.tokens_input, answer.tokens_output
        yield answer

    async def answer(self, query: str, run: ChatRun) -> Answer:
        """The whole Answer at once."""
        async for item in self.stream(query, run):
            if isinstance(item, Answer):
                return item
        raise RuntimeError("the answer stream ended without an answer")
