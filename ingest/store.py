"""Write documents and their chunks into Postgres.

One transaction per document: either all of its chunks land or none do, so an
interrupted run never leaves a half-ingested document behind.
"""

import logging
from collections.abc import Iterable, Iterator
from itertools import islice

import numpy as np
import psycopg
from config import DATABASE_URL, EMBEDDING_DIM
from models import Chunk, DocumentInfo

logger = logging.getLogger(__name__)

# Rows per COPY batch. Large enough to amortise the round trip, small enough
# that one batch of 768-dimension vectors stays a few megabytes.
COPY_BATCH = 500


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL)


def vector_literal(vector: np.ndarray) -> str:
    """pgvector's text form: [0.1,-0.2,...]. Six decimals is far more than
    float32 carries, so nothing is lost and rows stay compact."""
    if vector.shape != (EMBEDDING_DIM,):
        raise ValueError(f"expected a {EMBEDDING_DIM}-dimension vector, got {vector.shape}")
    return "[" + ",".join(f"{value:.6f}" for value in vector) + "]"


def is_unchanged(conn: psycopg.Connection, doc: DocumentInfo) -> bool:
    """True if this exact file has already been ingested.

    The check is the content hash, not the name or the date, so a re-downloaded
    but identical file is skipped and an edited one is re-ingested.
    """
    row = conn.execute(
        "SELECT sha256 FROM documents WHERE doc_id = %s",
        (doc.doc_id,),
    ).fetchone()
    return row is not None and row[0] == doc.sha256


def upsert_document(conn: psycopg.Connection, doc: DocumentInfo, chunk_count: int) -> None:
    """Insert the document, or update it if it is being re-ingested."""
    extra = doc.extra
    conn.execute(
        """
        INSERT INTO documents (
            doc_id, title, source_url, source_organization, document_type,
            celex_number, collection, publication_date, sha256, page_count,
            chunk_count, ingested_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
        ON CONFLICT (doc_id) DO UPDATE SET
            title = EXCLUDED.title,
            source_url = EXCLUDED.source_url,
            source_organization = EXCLUDED.source_organization,
            document_type = EXCLUDED.document_type,
            celex_number = EXCLUDED.celex_number,
            collection = EXCLUDED.collection,
            publication_date = EXCLUDED.publication_date,
            sha256 = EXCLUDED.sha256,
            page_count = EXCLUDED.page_count,
            chunk_count = EXCLUDED.chunk_count,
            ingested_at = now()
        """,
        (
            doc.doc_id,
            doc.title,
            doc.source_url,
            extra.get("source_organization"),
            extra.get("document_type"),
            extra.get("celex_number"),
            extra.get("collection"),
            extra.get("publication_date"),
            doc.sha256,
            doc.page_count,
            chunk_count,
        ),
    )


def _batched(items: Iterable, size: int) -> Iterator[list]:
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def replace_chunks(
    conn: psycopg.Connection,
    doc_id: str,
    pairs: Iterable[tuple[Chunk, np.ndarray]],
) -> int:
    """Delete this document's chunks and write the new ones.

    Delete-then-insert rather than updating in place: chunk boundaries move
    when the text or the chunk size changes, so old chunk numbers have no
    meaning. COPY rather than INSERT, because it is several times faster for
    thousands of rows.
    """
    conn.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))

    written = 0
    columns = "doc_id, chunk_index, text, page_start, page_end, embedding"
    for batch in _batched(pairs, COPY_BATCH):
        with conn.cursor().copy(f"COPY chunks ({columns}) FROM STDIN") as copy:
            for chunk, vector in batch:
                copy.write_row(
                    (
                        doc_id,
                        chunk.index,
                        chunk.text,
                        chunk.page_start,
                        chunk.page_end,
                        vector_literal(vector),
                    )
                )
        written += len(batch)
    return written


def store_document(
    conn: psycopg.Connection,
    doc: DocumentInfo,
    pairs: Iterable[tuple[Chunk, np.ndarray]],
) -> int:
    """Store one document and its chunks in a single transaction."""
    with conn.transaction():
        written = replace_chunks(conn, doc.doc_id, pairs)
        upsert_document(conn, doc, written)
    logger.info("stored %s: %d chunks", doc.doc_id, written)
    return written


def corpus_stats(conn: psycopg.Connection) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT (SELECT count(*) FROM documents),
               (SELECT count(*) FROM chunks),
               (SELECT count(*) FROM chunks WHERE embedding IS NULL)
        """
    ).fetchone()
    return {"documents": row[0], "chunks": row[1], "chunks_without_embedding": row[2]}


if __name__ == "__main__":
    with connect() as conn:
        print(corpus_stats(conn))
