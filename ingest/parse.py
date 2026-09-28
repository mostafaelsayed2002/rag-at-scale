"""Read a PDF into clean pages, and judge whether its text is usable.

Old acts are scans with an OCR text layer added by the Publications Office.
That layer is usually good, but carries artifacts that hurt search: words
broken across lines ("Euro- pean"), and running headers repeated on every
page. Keyword search in particular needs whole words.
"""

import re

import pymupdf
from models import Page

# Words split across a line break. A soft hyphen (U+00AD) is always a split;
# a plain hyphen only when a lowercase letter follows, so "non-\ndiscrimination"
# is not joined but "regu-\nlation" is. (The former is rarer than the harm of
# leaving every OCR split in place.)
SOFT_HYPHEN = re.compile(r"­\s*")
LINE_HYPHEN = re.compile(r"([a-z])-\n([a-z])")

# Lines that are page furniture rather than content: the Official Journal
# header, its issue reference ("L 119/1"), a bare date, a bare page number,
# and the language code printed on every page.
FURNITURE = re.compile(
    r"^\s*("
    r"Official Journal of the European (Union|Communities).*"
    r"|[LC]\s?\d+\s?/\s?\d+"
    r"|\d{1,2}\.\s?\d{1,2}\.\s?\d{2,4}"
    r"|\d{1,4}"
    r"|EN"
    r")\s*$",
    re.MULTILINE,
)
SPACES = re.compile(r"[ \t\u00a0]+")  # spaces, tabs, non-breaking spaces
BLANK_LINES = re.compile(r"\n{3,}")

# Frequent English words: a page of real text is full of them, garbled OCR
# and pure number tables are not.
COMMON_WORDS = frozenset(
    [
        "the", "of", "and", "to", "in", "a", "is", "for", "be", "shall", "by", "on",
        "that", "this", "with", "as", "or", "are", "from", "which", "member", "states",
        "article", "regulation", "directive", "decision", "council", "commission",
        "european", "union", "community",
    ]
)
WORD = re.compile(r"[A-Za-z]{2,}")

# Below these, a document is not worth indexing (measured on the oldest
# acts: fewer than 1 in 50 fall below them).
MIN_CHARS_PER_PAGE = 80
MIN_COMMON_WORD_RATIO = 0.06


def clean(text: str) -> str:
    text = SOFT_HYPHEN.sub("", text)
    text = LINE_HYPHEN.sub(r"\1\2", text)
    text = FURNITURE.sub("", text)
    text = SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return BLANK_LINES.sub("\n\n", text).strip()


def read_pages(path: str) -> tuple[list[Page], int]:
    """Cleaned pages with text, and the PDF's page count."""
    with pymupdf.open(path) as document:
        pages = []
        for page in document:
            text = clean(page.get_text())
            if text:
                pages.append(Page(number=page.number + 1, text=text))
        return pages, document.page_count


def quality(pages: list[Page], page_count: int) -> str:
    """'ok', or why the text is not worth indexing."""
    text = " ".join(p.text for p in pages)
    if len(text) < MIN_CHARS_PER_PAGE * max(page_count, 1):
        return "no_text"
    words = WORD.findall(text)
    common = sum(1 for w in words if w.lower() in COMMON_WORDS)
    if not words or common / len(words) < MIN_COMMON_WORD_RATIO:
        return "garbled"
    return "ok"
