"""Find the passages closest to a question vector."""

from langsmith import traceable

from ..core.config import settings
from ..db.pool import pool

# Rows fetched per passage wanted when recitals are capped: a third of the
# corpus is recitals, and they crowd the top, so the skipped ones need room.
OVERFETCH = 3


def is_recital(chunk: dict) -> bool:
    """A chunk's header ends with its label, e.g. "... | Recitals (14)-(15)"."""
    header = chunk["text"].split("\n", 1)[0]
    return header.rsplit(" | ", 1)[-1].startswith("Recitals")


@traceable(
    run_type="retriever",
    name="retrieve",
    process_inputs=lambda inputs: {
        "k": inputs.get("k"),
        "max_recitals": inputs.get("max_recitals"),
        "vector": "<hidden>",
    },
)
async def retrieve(vector: str, k: int, max_recitals: int | None = None) -> list[dict]:
    """The k passages closest to the query vector, with at most max_recitals
    recitals among them (None: no limit).

    Traced as a retriever so a trace shows which passages an answer was built
    from, which is what separates a retrieval problem from a prompting one.
    """
    rows = k if max_recitals is None else k * OVERFETCH
    async with pool.connection() as conn, conn.transaction():
        # SET LOCAL lasts only for this transaction, so a pooled connection
        # never carries the setting into another request.
        await conn.execute(f"SET LOCAL hnsw.ef_search = {int(settings.hnsw_ef_search)}")
        cur = await conn.execute(
            """
            SELECT c.id AS chunk_id, c.doc_id, d.title, c.text,
                   c.page_start, c.page_end,
                   1 - (c.embedding <=> %s::halfvec) AS score
            FROM chunks c
            JOIN documents d USING (doc_id)
            ORDER BY c.embedding <=> %s::halfvec
            LIMIT %s
            """,
            (vector, vector, rows),
        )
        found = await cur.fetchall()
    if max_recitals is None:
        return found

    chunks = []
    recitals = 0
    for chunk in found:
        if is_recital(chunk):
            if recitals == max_recitals:
                continue
            recitals += 1
        chunks.append(chunk)
        if len(chunks) == k:
            break
    return chunks
