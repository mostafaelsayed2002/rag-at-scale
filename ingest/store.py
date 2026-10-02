"""Write documents, chunks and their vectors into Postgres.

One transaction per shard: either all of a shard's documents land or none do,
so an interrupted load never leaves a half-loaded document behind.
"""

from collections.abc import Iterable

import numpy as np
import psycopg
from config import settings
from models import Chunk, DocumentInfo

# Readable groups for the resource types, used as the documents' collection.
COLLECTIONS = {"REG": "Regulation", "DIR": "Directive", "DEC": "Decision", "RECO": "Recommendation"}


class SchemaError(RuntimeError):
    pass


def connect() -> psycopg.Connection:
    """Autocommit, so each `conn.transaction()` below is a real transaction that
    commits when its shard is stored, not a savepoint inside one long session."""
    if not settings.database_url:
        raise SchemaError("DATABASE_URL is not set (in .env or the environment).")
    return psycopg.connect(settings.database_url, autocommit=True)


def check_schema(conn: psycopg.Connection) -> None:
    """Fail early and clearly if the database still has the old schema."""
    row = conn.execute(
        """
        SELECT format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute a
        WHERE a.attrelid = to_regclass('chunks') AND a.attname = 'embedding'
        """
    ).fetchone()
    expected = f"halfvec({settings.embedding_dim})"
    if row is None or row[0] != expected:
        found = row[0] if row else "no chunks table"
        raise SchemaError(
            f"chunks.embedding is {found}, expected {expected}. Recreate the "
            "documents and chunks tables from db/migrations/001_init.sql."
        )


def stored_hashes(conn: psycopg.Connection) -> dict[str, str]:
    return dict(conn.execute("SELECT doc_id, sha256 FROM documents").fetchall())


def halfvec(vector: np.ndarray) -> str:
    """pgvector's text form. Five decimals: more than half precision keeps."""
    return "[" + ",".join(f"{v:.5f}" for v in vector.astype(np.float32)) + "]"


def pg_text(value: str | None) -> str | None:
    """Postgres text cannot hold NUL (0x00) bytes, which a few PDFs' text
    layers contain (broken fonts, OCR). They carry no meaning, so drop them."""
    return value.replace("\x00", "") if value else value


def collection(act_type: str | None) -> str:
    base = (act_type or "").split("_")[0]
    return COLLECTIONS.get(base, "Other")


def store_shard(
    conn: psycopg.Connection,
    docs: list[DocumentInfo],
    chunks: list[Chunk],
    vectors: np.ndarray,
) -> int:
    """Replace these documents and their chunks in one transaction.

    Delete-then-insert rather than updating in place: chunk boundaries move
    when the text or chunk size changes, so old chunk numbers mean nothing.
    COPY rather than INSERT, because it is many times faster for bulk rows.
    """
    ids = [d.doc_id for d in docs]
    wanted = set(ids)
    rows: Iterable[tuple] = (
        (c.doc_id, c.index, pg_text(c.text), c.page_start, c.page_end, c.tokens, halfvec(v))
        for c, v in zip(chunks, vectors, strict=True)
        if c.doc_id in wanted
    )
    with conn.transaction():
        conn.execute("DELETE FROM chunks WHERE doc_id = ANY(%s)", (ids,))
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO documents (
                    doc_id, title, source_url, source_organization, document_type,
                    celex_number, collection, publication_date, topics, sha256,
                    page_count, chunk_count, ingested_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (doc_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    source_url = EXCLUDED.source_url,
                    document_type = EXCLUDED.document_type,
                    collection = EXCLUDED.collection,
                    publication_date = EXCLUDED.publication_date,
                    topics = EXCLUDED.topics,
                    sha256 = EXCLUDED.sha256,
                    page_count = EXCLUDED.page_count,
                    chunk_count = EXCLUDED.chunk_count,
                    ingested_at = now()
                """,
                [
                    (
                        d.doc_id,
                        pg_text(d.title),
                        f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{d.doc_id}",
                        "EU Publications Office",
                        d.act_type,
                        d.doc_id,
                        collection(d.act_type),
                        d.date,
                        d.topics,
                        d.sha256,
                        d.page_count,
                        d.chunk_count,
                    )
                    for d in docs
                ],
            )
        written = 0
        columns = "doc_id, chunk_index, text, page_start, page_end, tokens, embedding"
        with conn.cursor().copy(f"COPY chunks ({columns}) FROM STDIN") as copy:
            for row in rows:
                copy.write_row(row)
                written += 1
    return written


def corpus_stats(conn: psycopg.Connection) -> dict[str, int]:
    row = conn.execute(
        "SELECT (SELECT count(*) FROM documents), (SELECT count(*) FROM chunks)"
    ).fetchone()
    return {"documents": row[0], "chunks": row[1]}
