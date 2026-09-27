"""Find the passages closest to a question vector."""

from langsmith import traceable

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
    async with pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT c.id AS chunk_id, c.doc_id, d.title, c.text,
                   c.page_start, c.page_end,
                   1 - (c.embedding <=> %s::vector) AS score
            FROM chunks c
            JOIN documents d USING (doc_id)
            WHERE c.embedding IS NOT NULL
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
            """,
            (vector, vector, k),
        )
        return await cur.fetchall()
