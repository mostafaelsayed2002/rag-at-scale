from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .db import pool


class ChunkIn(BaseModel):
    text: str = Field(min_length=1)
    source: str | None = None


class Chunk(BaseModel):
    id: int
    text: str
    source: str | None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
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


@app.post("/chunks", response_model=Chunk, status_code=201)
async def create_chunk(chunk: ChunkIn):
    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO chunks (text, source) VALUES (%s, %s) RETURNING id, text, source",
            (chunk.text, chunk.source),
        )
        return await cur.fetchone()
