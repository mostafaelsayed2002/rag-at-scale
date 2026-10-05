"""Read the [n] markers in an answer and resolve them to the passages behind them."""

import logging
import re

from .types import Citation

logger = logging.getLogger(__name__)

# [1], or [1][2], or [1, 2] — the shapes a model actually produces.
CITATION = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


def cited_numbers(text: str) -> list[int]:
    """Source numbers cited in the answer, without duplicates, in first-seen order.

    Example: "Erase data [1]. Exceptions [2, 1] and [3]." -> [1, 2, 3]
    """
    seen: list[int] = []
    for match in CITATION.finditer(text):
        for part in match.group(1).split(","):
            number = int(part.strip())
            if number not in seen:
                seen.append(number)
    return seen


def collect_citations(text: str, chunks: list[dict]) -> list[Citation]:
    """Turn the cited numbers into Citation objects for the UI's source cards.

    [n] points to the n-th passage. Numbers with no passage (e.g. [9] when
    there are 6) are made up by the model, so they are logged and dropped.
    """
    citations = []
    for number in cited_numbers(text):
        if not 1 <= number <= len(chunks):
            logger.warning("answer cited [%d] with only %d sources", number, len(chunks))
            continue
        chunk = chunks[number - 1]
        # The first line is the header added for search ("act | chapter |
        # Article 6 ..."). It is not on the PDF page, so the viewer could not
        # find a quote starting with it: 7 of 20 passages found with it, 20 of
        # 20 without.
        body = chunk["text"].split("\n", 1)[-1]
        citations.append(
            Citation(
                n=number,
                chunk_id=chunk["chunk_id"],
                doc_id=chunk["doc_id"],
                title=chunk.get("title"),
                page_start=chunk["page_start"],
                page_end=chunk["page_end"],
                quote=body,
                score=chunk["score"],
            )
        )
    return citations
