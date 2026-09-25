"""Search the corpus, list its documents, and serve the PDFs behind citations."""

import logging
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .analytics import overview
from .cache import build_cache
from .config import settings
from .db import pool
from .embeddings import build_embedder, embed_query
from .llm import Answer, answer_question, build_llm
from .models import ChatRequest, ChatResponse, MatricsResponse
from .monitoring import Metrics, MetricsMiddleware, setup_logging

logger = logging.getLogger(__name__)


class DocumentSummary(BaseModel):
    doc_id: str
    title: str | None
    collection: str | None
    document_type: str | None
    source_url: str | None
    page_count: int | None
    chunk_count: int | None


class Document(DocumentSummary):
    source_organization: str | None
    celex_number: str | None
    publication_date: str | None
    has_file: bool


class SearchHit(BaseModel):
    chunk_id: int
    doc_id: str
    title: str | None
    text: str
    page_start: int
    page_end: int
    # 1 is identical, 0 is unrelated: cosine distance subtracted from one, so
    # the number reads the way people expect a relevance score to.
    score: float


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
    await pool.open()
    # The middleware reaches the database through this, so it does not have to
    # import the pool itself.
    app.state.pool = pool
    app.state.pdfs = index_pdfs(settings.data_dir)
    app.state.embedder = build_embedder() if settings.google_api_key else None
    app.state.llm = build_llm() if settings.google_api_key else None
    app.state.cache = build_cache()
    # Shares the cache's connection: one client is enough, and a second pool
    # to the same Redis would buy nothing.
    app.state.metrics = Metrics(app.state.cache.client)
    yield
    await pool.close()
    if app.state.cache.client is not None:
        await app.state.cache.client.aclose()


app = FastAPI(title="RAG at Scale", lifespan=lifespan)

# The last middleware added is the outermost, so CORS below wraps this one.
# That is the order we want: CORS headers are attached even to responses this
# one counted as errors, and browser preflights are answered without being
# measured as traffic.
app.add_middleware(MetricsMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics", response_model=MatricsResponse)
async def metrics():
    """Live counters, shared by every worker through Redis."""
    return await app.state.metrics.summary()


@app.get("/analytics")
async def analytics(hours: int = Query(default=24, ge=1, le=720)):
    """What the dashboard shows: percentiles, trends and corpus facts.

    Computed from request_log rather than from the counters, because a counter
    cannot produce a percentile or a series.
    """
    return await overview(pool, app.state.cache.client, hours)


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


async def embed_cached(q: str) -> tuple[str, bool]:
    """The query vector, and whether it came from the cache.

    Shared by search and chat: embedding is a paid network call, and the same
    question always produces the same vector. The key includes the model,
    because vectors from two models are not comparable.
    """
    if app.state.embedder is None:
        raise HTTPException(status_code=503, detail="This needs GOOGLE_API_KEY")

    fingerprint = f"{settings.embedding_model}:{settings.embedding_dim}:{q}"
    vector = await app.state.cache.get("embed", fingerprint)
    if vector is not None:
        return vector, True

    try:
        vector = embed_query(app.state.embedder, q)
    except Exception as exc:
        # The query has to be embedded before anything can be retrieved, so an
        # exhausted quota is reported as such rather than as a server fault.
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message:
            logger.warning("embedding quota exhausted: %s", message)
            raise HTTPException(
                status_code=429,
                detail="The embedding quota is used up, so search is unavailable right now.",
            ) from exc
        raise

    await app.state.cache.set("embed", fingerprint, vector)
    return vector, False


async def retrieve(vector: str, k: int, collection: str | None = None) -> list[dict]:
    """The k passages closest to the query vector."""
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT c.id AS chunk_id, c.doc_id, d.title, c.text,
                   c.page_start, c.page_end,
                   1 - (c.embedding <=> %s::vector) AS score
            FROM chunks c
            JOIN documents d USING (doc_id)
            WHERE c.embedding IS NOT NULL
              AND (%s::text IS NULL OR d.collection = %s)
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
            """,
            (vector, collection, collection, vector, k),
        )
        return await cur.fetchall()


@app.get("/search", response_model=list[SearchHit])
async def search(
    request: Request,
    q: str = Query(min_length=1, description="what to search for"),
    k: int = Query(default=10, ge=1, le=50, description="how many results"),
    collection: str | None = Query(default=None, description="restrict to one collection"),
):
    """The passages themselves, without an answer written over them."""
    clock = Stopwatch()
    with clock("embedding"):
        vector, hit = await embed_cached(q)
    with clock("retrieval"):
        hits = await retrieve(vector, k, collection)

    # Left for the metrics middleware, which runs after this and cannot see
    # what happened inside the endpoint.
    request.state.cache_hit = hit
    request.state.stages = clock.stages
    return hits


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    """Retrieve passages, then have the model write an answer that cites them.

    The whole answer is cached, not just the embedding: at temperature zero
    the same question produces the same answer, so serving the stored one is
    honest rather than merely convenient, and costs no tokens at all.
    """
    if app.state.llm is None:
        raise HTTPException(status_code=503, detail="Chat needs GOOGLE_API_KEY")

    started = time.perf_counter()
    clock = Stopwatch()
    # Recorded for the history: the question arrives in the body, which the
    # middleware cannot read.
    request.state.query = body.query

    # The model and k belong in the key: change either and the stored answer
    # is no longer the answer this configuration would produce.
    fingerprint = f"{settings.llm_model}:{settings.retrieve_k}:{body.query}"
    stored = await app.state.cache.get("answer", fingerprint)
    request.state.cache_hit = stored is not None

    if stored is not None:
        answer = Answer.model_validate_json(stored)
    else:
        with clock("embedding"):
            vector, _ = await embed_cached(body.query)
        with clock("retrieval"):
            chunks = await retrieve(vector, settings.retrieve_k)
        try:
            with clock("generation"):
                answer = await answer_question(app.state.llm, body.query, chunks)
        except Exception as exc:
            message = str(exc)
            if "RESOURCE_EXHAUSTED" in message or "429" in message:
                logger.warning("generation quota exhausted: %s", message)
                raise HTTPException(
                    status_code=429,
                    detail="The model quota is used up, so answering is unavailable right now.",
                ) from exc
            raise
        await app.state.cache.set("answer", fingerprint, answer.model_dump_json())

    request.state.stages = clock.stages

    # Read by the metrics middleware. Only a generated answer spent tokens:
    # a cached one is replayed from Redis and calls nothing, so counting its
    # stored numbers again would bill the same generation twice. The response
    # below still reports them, because they are what that answer cost.
    if stored is None:
        request.state.tokens_input = answer.tokens_input
        request.state.tokens_output = answer.tokens_output

    return ChatResponse(
        response=answer.text,
        citations=answer.citations,
        thread_id=body.thread_id,
        model_used=settings.llm_model,
        cached=stored is not None,
        retrieved_chunks=answer.retrieved,
        tokens_input=answer.tokens_input,
        tokens_output=answer.tokens_output,
        processing_time=round(time.perf_counter() - started, 3),
    )
