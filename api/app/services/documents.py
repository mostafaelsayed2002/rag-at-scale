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


def _escape_like(word: str) -> str:
    """Make %, _ and \\ in user input match literally in ILIKE."""
    return word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def list_documents(
    q: str | None, collection: str | None, limit: int, offset: int
) -> dict:
    """One page of acts, newest first. Every word of `q` must appear in the
    title or the CELEX number, so "gdpr" and "2016/679" both find the GDPR."""
    where, params = [], []
    for word in (q or "").split()[:8]:
        where.append("(title ILIKE %s OR doc_id ILIKE %s)")
        pattern = f"%{_escape_like(word)}%"
        params += [pattern, pattern]
    if collection:
        where.append("collection = %s")
        params.append(collection)
    clause = f"WHERE {' AND '.join(where)}" if where else ""

    async with pool.connection() as conn:
        total = (
            await (await conn.execute(f"SELECT count(*) AS n FROM documents {clause}", params)).fetchone()
        )["n"]
        items = await (
            await conn.execute(
                f"""
                SELECT doc_id, title, collection, document_type, source_url,
                       publication_date::text AS publication_date, page_count, chunk_count
                FROM documents {clause}
                -- With a search, titles that name it early come first: the GDPR's
                -- title starts "Regulation (EU) 2016/679", while acts that only
                -- refer to it mention it further in. Then newest first.
                ORDER BY coalesce(nullif(strpos(lower(title), lower(%s)), 0), 1000000),
                         publication_date DESC NULLS LAST, doc_id
                LIMIT %s OFFSET %s
                """,
                [*params, (q or "").strip(), limit, offset],
            )
        ).fetchall()
        collections = await (
            await conn.execute(
                """
                SELECT collection AS name, count(*) AS count FROM documents
                GROUP BY collection ORDER BY count(*) DESC
                """
            )
        ).fetchall()
        corpus = await (
            await conn.execute(
                "SELECT count(*) AS documents, coalesce(sum(chunk_count), 0) AS chunks FROM documents"
            )
        ).fetchone()
    return {"total": total, "items": items, "collections": collections, "corpus": corpus}


async def get_document(doc_id: str) -> dict | None:
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT doc_id, title, collection, document_type, source_url,
                   page_count, chunk_count, source_organization, celex_number,
                   publication_date::text AS publication_date, topics
            FROM documents
            WHERE doc_id = %s
            """,
            (doc_id,),
        )
        return await cur.fetchone()
