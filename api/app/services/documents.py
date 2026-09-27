"""The ingested documents and the PDFs behind them."""

import logging
from pathlib import Path

from ..db.pool import pool

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


async def list_documents() -> list[dict]:
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


async def get_document(doc_id: str) -> dict | None:
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
        return await cur.fetchone()
