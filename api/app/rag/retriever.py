"""Find the passages closest to a question vector."""

from langsmith import traceable

from ..core.config import settings
from ..db.pool import pool


@traceable(
    run_type="retriever",
    name="retrieve",
    process_inputs=lambda inputs: {"k": inputs.get("k"), "vector": "<hidden>"},
)
async def retrieve(vector: str, k: int) -> list[dict]:
    """The k passages closest to the query vector.

    Traced as a retriever so a trace shows which passages an answer was built
    from, which is what separates a retrieval problem from a prompting one.
    """
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
            (vector, vector, k),
        )
        return await cur.fetchall()
