"""App entry point: startup and shutdown, middleware, error handlers and routes.

Everything else lives in its layer:
    core/      config, logging, tracing, errors, timing
    api/       routes and their dependencies
    schemas/   request and response bodies
    rag/       the pipeline: embed, retrieve, generate, cite (no HTTP)
    services/  cache, documents, request log, analytics
    db/        the Postgres pool
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langsmith import tracing_context

from .api.routes import analytics, chat, documents, health
from .core.config import settings
from .core.errors import register_error_handlers
from .core.logging import setup_logging
from .core.rate_limit import limiter
from .core.tracing import configure as configure_tracing
from .db.pool import pool
from .rag.embedder import build_embedder, embed_query
from .rag.reranker import build_reranker
from .rag.generator import build_llm
from .rag.pipeline import RagPipeline
from .rag.retriever import retrieve
from .services.cache import build_cache
from .services.documents import index_pdfs


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level, as_json=settings.is_production)
    # Before the model is built: the client reads the environment when it is
    # constructed, so configuring afterwards would trace nothing.
    configure_tracing()
    await pool.open()
    cache = build_cache()
    app.state.pdfs = index_pdfs(settings.data_dir)
    embedder = build_embedder()
    # One real search at startup: it opens a database connection and pulls the
    # top of the HNSW graph into memory, so the first user does not wait ~2 s
    # (measured: first search 1,751 ms, then 5-8 ms). Kept out of LangSmith.
    with tracing_context(enabled=False):
        await retrieve(await embed_query(embedder, "warm up"), settings.retrieve_k)
    app.state.pipeline = RagPipeline(
        cache=cache, embedder=embedder, reranker=build_reranker(), llm=build_llm()
    )
    yield
    await pool.close()
    await cache.client.aclose()


app = FastAPI(title="RAG at Scale", lifespan=lifespan)
app.state.limiter = limiter  # slowapi looks for it here

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
register_error_handlers(app)

for module in (health, chat, documents, analytics):
    app.include_router(module.router)
