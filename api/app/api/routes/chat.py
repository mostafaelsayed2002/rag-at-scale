import asyncio
import json
import logging
import time

import anyio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from ...core.config import settings
from ...core.errors import QuotaExhausted
from ...core.rate_limit import limiter
from ...db.pool import pool
from ...rag.pipeline import ChatRun
from ...rag.types import Answer
from ...schemas.chat import ChatRequest, ChatResponse
from ...services.request_log import record_chat
from ..deps import Pipeline

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
@limiter.limit(settings.rate_limit)
# `request` is unused here but required: slowapi reads the client IP from it.
async def chat(request: Request, body: ChatRequest, pipeline: Pipeline):
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


def sse(event: str, data: dict) -> str:
    """One Server-Sent Event: a name, a JSON payload and a blank line."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.post("/chat/stream")
@limiter.limit(settings.rate_limit)
async def chat_stream(request: Request, body: ChatRequest, pipeline: Pipeline):
    """The answer as Server-Sent Events, so the reader sees it being written:

        token  {"text": ...}       a piece of the answer, as the model writes it
        done   ChatResponse        the whole answer, its citations and costs
        error  {"message": ...}    nothing more is coming

    Citations come with "done": they are read from the whole text. A cached
    answer arrives as one token followed by done.
    """

    async def events():
        started = time.perf_counter()
        run = ChatRun()
        status = 500
        streamed = False
        try:
            async for item in pipeline.stream(body.query, run):
                if isinstance(item, Answer):
                    answer = item
                else:
                    streamed = True
                    yield sse("token", {"text": item})
            if not streamed:  # a cached answer: the text in one piece
                yield sse("token", {"text": answer.text})
            status = 200
            done = ChatResponse(
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
            yield sse("done", done.model_dump(mode="json"))
        except QuotaExhausted as exc:
            status = 429
            yield sse("error", {"message": exc.detail})
        except asyncio.CancelledError:
            status = 499  # the reader left (closed the tab, pressed stop)
            raise
        except Exception:
            logger.exception("streamed answer failed")
            yield sse("error", {"message": "The answer could not be generated. Please try again."})
        finally:
            # Shielded: when the reader leaves, the stream is cancelled, and an
            # unshielded write would be cancelled with it.
            with anyio.CancelScope(shield=True):
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

    # no-cache and X-Accel-Buffering: proxies must pass each event on at once.
    headers = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    return StreamingResponse(events(), media_type="text/event-stream", headers=headers)
