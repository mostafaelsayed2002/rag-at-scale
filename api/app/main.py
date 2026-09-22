"""Search the corpus, list its documents, and serve the PDFs behind citations."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import settings
from .db import pool
from .embeddings import build_embedder, embed_query

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
    await pool.open()
    app.state.pdfs = index_pdfs(settings.data_dir)
    app.state.embedder = build_embedder() if settings.google_api_key else None
    yield
    await pool.close()


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


@app.get("/search", response_model=list[SearchHit])
async def search(
    q: str = Query(min_length=1, description="what to search for"),
    k: int = Query(default=10, ge=1, le=50, description="how many results"),
    collection: str | None = Query(default=None, description="restrict to one collection"),
):
    if app.state.embedder is None:
        raise HTTPException(status_code=503, detail="Search needs GOOGLE_API_KEY")

    try:
        vector = embed_query(app.state.embedder, q)
    except Exception as exc:
        # The query has to be embedded before anything can be searched, so an
        # exhausted quota is reported as such rather than as a server fault.
        message = str(exc)
        if "RESOURCE_EXHAUSTED" in message or "429" in message:
            logger.warning("embedding quota exhausted: %s", message)
            raise HTTPException(
                status_code=429,
                detail="The embedding quota is used up, so search is unavailable right now.",
            ) from exc
        raise

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
