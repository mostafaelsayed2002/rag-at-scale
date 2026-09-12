from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastembed import TextEmbedding
from pydantic import BaseModel, Field

from .db import pool

# Must match the model the corpus was embedded with: vectors from two different
# models are not comparable, and the distance would be meaningless rather than
# obviously wrong.
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


class ChunkIn(BaseModel):
    text: str = Field(min_length=1)
    source: str | None = None


class Chunk(BaseModel):
    id: int
    text: str
    source: str | None


class SearchHit(Chunk):
    # 1 is identical, 0 is unrelated. Cosine distance subtracted from one, so
    # the number reads the way people expect a relevance score to read.
    score: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    # Loaded once: the weights take a second or two to read, and no request
    # should pay that.
    app.state.embedder = TextEmbedding(EMBEDDING_MODEL)
    yield
    await pool.close()


app = FastAPI(title="RAG at Scale", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/chunks", response_model=list[Chunk])
async def list_chunks():
    async with pool.connection() as conn:
        cur = await conn.execute(
            "SELECT id, text, source FROM chunks ORDER BY created_at DESC LIMIT 50"
        )
        return await cur.fetchall()


def embed(text: str) -> str:
    """Embed one string and render it as a pgvector literal."""
    # embed() returns a generator over a batch; there is one item here.
    vector = next(iter(app.state.embedder.embed([text])))
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


@app.get("/search", response_model=list[SearchHit])
async def search(
    q: str = Query(min_length=1, description="what to search for"),
    k: int = Query(default=10, ge=1, le=50, description="how many results"),
):
    literal = embed(q)

    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT id, text, source, 1 - (embedding <=> %s::vector) AS score
            FROM chunks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (literal, literal, k),
        )
        return await cur.fetchall()


@app.post("/chunks", response_model=Chunk, status_code=201)
async def create_chunk(chunk: ChunkIn):
    # Embedded on the way in: a chunk without a vector can never be found,
    # which makes an unembedded row worse than no row at all.
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            INSERT INTO chunks (text, source, embedding)
            VALUES (%s, %s, %s::vector)
            RETURNING id, text, source
            """,
            (chunk.text, chunk.source, embed(chunk.text)),
        )
        return await cur.fetchone()
