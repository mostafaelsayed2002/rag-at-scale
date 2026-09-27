import time

from fastapi import APIRouter, HTTPException

from ...core.config import settings
from ...core.errors import QuotaExhausted
from ...db.pool import pool
from ...rag.pipeline import ChatRun
from ...schemas.chat import ChatRequest, ChatResponse
from ...services.request_log import record_chat
from ..deps import Pipeline

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, pipeline: Pipeline):
    """Answer a question with citations: cache → embed → retrieve → generate.

    A cache hit returns the stored answer and skips the other steps.
    """
    started = time.perf_counter()
    run = ChatRun()
    # Measured below, in finally, so a failed request is recorded too.
    status = 500

    try:
        answer = await pipeline.answer(body.query, run)
        status = 200
        return ChatResponse(
            response=answer.text,
            citations=answer.citations,
            thread_id=body.thread_id,
            model_used=settings.llm_model,
            cached=run.cache_hit,
            retrieved_chunks=answer.retrieved,
            tokens_input=answer.tokens_input,
            tokens_output=answer.tokens_output,
            processing_time=round(time.perf_counter() - started, 3),
        )
    except QuotaExhausted:
        status = 429  # turned into the response by core.errors
        raise
    except HTTPException as exc:
        status = exc.status_code
        raise
    finally:
        await record_chat(
            pool,
            query=body.query,
            latency_ms=(time.perf_counter() - started) * 1000,
            status=status,
            cache_hit=run.cache_hit,
            tokens_input=run.tokens_input,
            tokens_output=run.tokens_output,
            stages=run.clock.stages,
        )
