"""Chat over the corpus, list its documents, and serve the PDFs behind citations."""

import logging
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from langsmith import traceable

from .analytics import overview
from .cache import build_cache
from .config import settings
from .db import pool
from .embeddings import build_embedder, embed_query
from .llm import Answer, answer_question, build_llm
from .models import ChatRequest, ChatResponse, Document, DocumentSummary
from .monitoring import record_chat, setup_logging
from .tracing import configure as configure_tracing

logger = logging.getLogger(__name__)


def index_pdfs(data_dir: Path) -> dict[str, Path]:
    """Map document id to file, so a citation can open the original PDF.

    Built once at startup by walking the corpus. Requests look the id up in
    this map rather than joining it onto a path, which also means a crafted id
    cannot reach a file outside the corpus.
    """
    if not data_dir.is_dir():
        logger.warning("no corpus directory at %s; PDFs will not be served", data_dir)
        return {}
    files = {path.stem: path for path in sorted(data_dir.rglob("*.pdf"))}
    logger.info("indexed %d PDFs under %s", len(files), data_dir)
    return files


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level, as_json=settings.is_production)
    # Before the model is built: the client reads the environment when it is
    # constructed, so configuring afterwards would trace nothing.
    configure_tracing()
    await pool.open()
    app.state.pdfs = index_pdfs(settings.data_dir)
    app.state.embedder = build_embedder()
    app.state.llm = build_llm()
    app.state.cache = build_cache()
    yield
    await pool.close()
    await app.state.cache.client.aclose()


app = FastAPI(title="RAG at Scale", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/analytics")
async def analytics(hours: int = Query(default=24, ge=1, le=720)):
    """Chat analytics for the last `hours`: latency percentiles, trends, cost and corpus stats."""
    return await overview(pool, hours)


@app.get("/documents", response_model=list[DocumentSummary])
async def list_documents():
    """Every ingested document, for the documents panel."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT doc_id, title, collection, document_type, source_url,
                   page_count, chunk_count
            FROM documents
            ORDER BY collection, title NULLS LAST, doc_id
            """
        )
        return await cur.fetchall()


@app.get("/documents/{doc_id}", response_model=Document)
async def get_document(doc_id: str):
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT doc_id, title, collection, document_type, source_url,
                   page_count, chunk_count, source_organization, celex_number,
                   publication_date::text AS publication_date
            FROM documents
            WHERE doc_id = %s
            """,
            (doc_id,),
        )
        row = await cur.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"No document {doc_id!r}")
    return {**row, "has_file": doc_id in app.state.pdfs}


@app.get("/documents/{doc_id}/file")
async def get_document_file(doc_id: str):
    """The original PDF, so the viewer can show the cited page itself.

    FileResponse answers range requests, which is what lets the viewer fetch
    one page instead of the whole file.
    """
    path = app.state.pdfs.get(doc_id)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail=f"No PDF for {doc_id!r}")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{doc_id}.pdf",
        content_disposition_type="inline",
        # The corpus is static: let the browser keep it for a day.
        headers={"Cache-Control": "public, max-age=86400"},
    )


class Stopwatch:
    """Times the parts of a request, so a slow answer says which part to fix."""

    def __init__(self):
        self.stages: dict[str, float] = {}

    @contextmanager
    def __call__(self, stage: str):
        started = time.perf_counter()
        try:
            yield
        finally:
            self.stages[stage] = round((time.perf_counter() - started) * 1000, 2)


def embed(q: str) -> str:
    """The question as a pgvector literal, ready to compare against the corpus."""
    try:
        return embed_query(app.state.embedder, q)
    except Exception as exc:
        # The question has to be embedded before anything can be retrieved, so
        # an exhausted quota is reported as such rather than as a server fault.
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message:
            logger.warning("embedding quota exhausted: %s", message)
            raise HTTPException(
                status_code=429,
                detail="The embedding quota is used up, so chat is unavailable right now.",
            ) from exc
        raise


async def generate(query: str, chunks: list[dict]) -> Answer:
    """The cited answer, with an exhausted model quota reported as 429."""
    try:
        return await answer_question(app.state.llm, query, chunks)
    except Exception as exc:
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message:
            logger.warning("generation quota exhausted: %s", message)
            raise HTTPException(
                status_code=429,
                detail="The model quota is used up, so answering is unavailable right now.",
            ) from exc
        raise


@traceable(run_type="retriever", name="retrieve")
async def retrieve(vector: str, k: int) -> list[dict]:
    """The k passages closest to the query vector.

    Traced as a retriever so a trace shows which passages an answer was built
    from, which is what separates a retrieval problem from a prompting one.
    """
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT c.id AS chunk_id, c.doc_id, d.title, c.text,
                   c.page_start, c.page_end,
                   1 - (c.embedding <=> %s::vector) AS score
            FROM chunks c
            JOIN documents d USING (doc_id)
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
            """,
            (vector, vector, k),
        )
        return await cur.fetchall()


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    """Answer a question with citations: cache → embed → retrieve → generate.

    A cache hit returns the stored answer and skips the other steps.
    """
    started = time.perf_counter()
    clock = Stopwatch()
    # Measured below, in finally, so a failed request is recorded too.
    status = 500
    cache_hit = False
    tokens_input = tokens_output = 0

    try:
        # The model and k belong in the key: change either and the stored
        # answer is no longer the one this configuration would produce.
        fingerprint = f"{settings.llm_model}:{settings.retrieve_k}:{body.query}"
        stored = await app.state.cache.get(fingerprint)
        cache_hit = stored is not None

        if stored is not None:
            answer = Answer.model_validate_json(stored)
        else:
            with clock("embedding"):
                vector = embed(body.query)
            with clock("retrieval"):
                chunks = await retrieve(vector, settings.retrieve_k)
            with clock("generation"):
                answer = await generate(body.query, chunks)
            await app.state.cache.set(fingerprint, answer.model_dump_json())
            # Only a generated answer spent tokens; a cached one cost nothing.
            tokens_input, tokens_output = answer.tokens_input, answer.tokens_output

        status = 200
        return ChatResponse(
            response=answer.text,
            citations=answer.citations,
            thread_id=body.thread_id,
            model_used=settings.llm_model,
            cached=cache_hit,
            retrieved_chunks=answer.retrieved,
            tokens_input=answer.tokens_input,
            tokens_output=answer.tokens_output,
            processing_time=round(time.perf_counter() - started, 3),
        )
    except HTTPException as exc:
        status = exc.status_code
        raise
    finally:
        await record_chat(
            pool,
            query=body.query,
            latency_ms=(time.perf_counter() - started) * 1000,
            status=status,
            cache_hit=cache_hit,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            stages=clock.stages,
        )
