"""Chunk an act by its legal structure instead of by size.

The size-based chunker (chunk.py) cuts every ~1,600 characters, wherever that
lands: mid-sentence, through a list, across two articles. EU acts have a clear
shape, and this follows it:

    title, citations, recitals (1) (2) ...   ->  recital chunks
    HAVE ADOPTED THIS REGULATION:
    Article 1 ... Article 99                 ->  one chunk per article
    ANNEX I ...                              ->  annex chunks

Every chunk starts with a header naming the act and the part, e.g.
"Regulation (EU) 2016/679 ... | Chapter III Rights of the data subject |
Article 15 Right of access by the data subject", so a chunk that says
"...within 72 hours..." also says which law and which article it is.

Acts without that shape (reports, notices, old decisions) fall back to
size-based pieces, still with the act's title as header.
"""

import re
from dataclasses import dataclass

import pymupdf
from langchain_text_splitters import RecursiveCharacterTextSplitter

# --- Reading the PDF ------------------------------------------------------

# Page furniture the old cleaner misses: the post-2023 Official Journal footer
# ("OJ L, 12.7.2024", "44/144", "ELI: http://..."), and OCR'd headers with
# spaces inside ("22 . 7 . 92", "No L 206 / 9").
FURNITURE = re.compile(
    r"^\s*("
    r"Official Journal of the European (Union|Communities).*"
    r"|OJ [LC],? ?\d{1,2}\.\d{1,2}\.\d{4}"
    r"|ELI: ?http\S*"
    r"|\d{1,4} ?/ ?\d{1,4}"
    r"|(No )?[LC] ?\d+ ?/ ?\d+"
    r"|\d{1,2} ?\. ?\d{1,2} ?\. ?\d{2,4}"
    r"|EN"
    r"|\\"
    r")\s*$",
    re.MULTILINE,
)
SOFT_HYPHEN = re.compile(r"­\s*")
LINE_HYPHEN = re.compile(r"([a-z])-\n([a-z])")
# "S e c t i o n" -> "Section": runs of 4+ single letters separated by spaces.
SPACED_WORD = re.compile(r"\b(?:[A-Za-z] ){3,}[A-Za-z]\b")
SPACES = re.compile(r"[ \t ]+")
BLANK_LINES = re.compile(r"\n{3,}")
# A paragraph or point number alone on its line ("1." / "(a)"): join it to its text.
LONE_NUMBER = re.compile(r"^(\d+ ?\.|\([a-z0-9]+\))\n(?=\S)", re.MULTILINE)
# A row of dots from a table of contents.
DOT_LEADERS = re.compile(r"( ?\. ?){5,}")


def clean(text: str) -> str:
    """Remove page furniture and OCR artifacts from one page of text."""
    text = text.replace("\x00", "")
    text = SOFT_HYPHEN.sub("", text)
    text = LINE_HYPHEN.sub(r"\1\2", text)
    text = SPACED_WORD.sub(lambda m: m.group(0).replace(" ", ""), text)
    text = DOT_LEADERS.sub(" ", text)
    text = SPACES.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = FURNITURE.sub("", text)
    text = LONE_NUMBER.sub(r"\1 ", text)
    return BLANK_LINES.sub("\n\n", text).strip()


def page_text(page: pymupdf.Page) -> str:
    """The page's text in reading order.

    Old Official Journal pages are printed in two columns, and their text
    layer often interleaves them line by line. When a page clearly has two
    columns, read the left column before the right one, section by section
    (a full-width block, such as a title, starts a new section).
    """
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    middle = page.rect.width / 2
    left = [b for b in blocks if b[2] < middle + 10]
    right = [b for b in blocks if b[0] > middle - 10]
    if len(left) < 3 or len(right) < 3:
        return page.get_text()  # one column: the default order is right

    ordered = []
    section_left = []
    section_right = []
    for block in sorted(blocks, key=lambda b: b[1]):  # top to bottom
        if block in left:
            section_left.append(block)
        elif block in right:
            section_right.append(block)
        else:  # full width: finish the current section first
            ordered += section_left + section_right
            section_left, section_right = [], []
            ordered.append(block)
    ordered += section_left + section_right
    return "\n".join(b[4] for b in ordered)


def read_pages(path: str) -> list[tuple[int, str]]:
    """(page number, cleaned text) for every page that has text."""
    pages = []
    with pymupdf.open(path) as document:
        for page in document:
            text = clean(page_text(page))
            if text:
                pages.append((page.number + 1, text))
    return pages


# --- Finding the structure --------------------------------------------------

ADOPTED = re.compile(r"^.{0,40}HA(?:S|VE) (?:ADOPTED|DECIDED)\b.*$", re.MULTILINE)
# Title case only: all-caps "ARTICLE 10" turns up in tables of contents.
ARTICLE = re.compile(r"^Article (\d+[a-z]*)[ \t]*$", re.MULTILINE)
ANNEX = re.compile(r"^ANNEX(?: [IVXLC]+| \d+)?\s*$", re.MULTILINE)
DIVISION = re.compile(
    r"^(CHAPTER|Chapter|TITLE|Title|SECTION|Section|PART|Part) [IVXLC\d]+[ \t]*$", re.MULTILINE
)
RECITAL_START = re.compile(r"\n(?=\(\d+\) |Whereas )")
PARAGRAPH_START = re.compile(r"\n(?=\d+\. )")

TITLE_CHARS = 250  # the act's title in each header is cut to this


@dataclass
class Piece:
    """One chunk before counting: where it sits in the act, and its text."""

    section: str  # "preamble", "article", "annex" or "body"
    label: str  # e.g. "Article 15 Right of access by the data subject"
    text: str
    start: int  # character offset in the full text, for page numbers


# Words a wrapped sentence line often ends on, but a title never does.
CONTINUES = {"the", "of", "this", "and", "to", "in", "a", "an", "for", "by", "with", "or", "that", "on", "as"}


def heading_title(body: str) -> tuple[str, str]:
    """Split a short title line off the start of an article, if there is one.

    Modern acts give every article a title ("Right of access by the data
    subject"); older ones start straight with the text, whose first line is
    then just a wrapped piece of a sentence.
    """
    first, _, rest = body.partition("\n")
    first = first.strip()
    rest = rest.strip()
    if not first or not rest or len(first) > 120:
        return "", body
    if first[0].isdigit() or first.startswith("("):
        return "", body  # a numbered paragraph, not a title
    if first.endswith((".", ";", ":", ",")):
        return "", body  # a sentence
    if first.split()[-1].lower() in CONTINUES:
        return "", body  # a sentence that goes on on the next line
    if not (rest[0].isupper() or rest[0].isdigit() or rest[0] == "("):
        return "", body  # the next line continues it
    return first, rest


def find_divisions(full: str) -> list[tuple[int, str, str]]:
    """Every CHAPTER/TITLE/PART/SECTION heading: (position, level, text with
    its title line), e.g. (51200, "top", "CHAPTER III Rights of the data subject")."""
    divisions = []
    for match in DIVISION.finditer(full):
        line_end = full.find("\n", match.end() + 1)
        title = full[match.end() + 1 : line_end if line_end > 0 else len(full)].strip()
        if len(title) > 120 or ARTICLE.match(title):
            title = ""
        level = "sub" if match.group(1).lower() == "section" else "top"
        divisions.append((match.start(), level, f"{match.group(0).strip()} {title}".strip()))
    return divisions


def division_at(divisions: list, position: int) -> str:
    """The chapter (and section, if any) an article at this position is in."""
    top = ""
    sub = ""
    for start, level, text in divisions:
        if start > position:
            break
        if level == "top":
            top, sub = text, ""
        else:
            sub = text
    return " | ".join(part for part in (top, sub) if part)


def drop_division_lines(body: str) -> str:
    """Remove CHAPTER/SECTION headings (and their title lines) from an
    article's text: they sit at its end but belong to the next article."""
    lines = body.split("\n")
    kept = []
    skip_next = False
    for line in lines:
        if skip_next:
            skip_next = False
            if len(line) <= 120:
                continue
        if DIVISION.match(line):
            skip_next = True
            continue
        kept.append(line)
    return "\n".join(kept)


def article_headings(full: str, start: int) -> list[re.Match]:
    """The act's "Article N" headings, in order. The run ends where the number
    starts again at 1 (a correlation table) or drops back a lot (a lone
    "Article 49" reference in an annex). Small drops are kept: old scans read
    in a slightly jumbled order (Article 6 before Article 4). A line that jumps
    far ahead ("Article 111" after Article 24) is a reference, not a heading."""
    headings = []
    previous = 0
    for match in ARTICLE.finditer(full, start):
        number = int(re.match(r"\d+", match.group(1)).group())
        if headings and number > previous + 20:
            continue
        if headings and (number == 1 or number < previous - 3):
            break
        headings.append(match)
        previous = max(previous, number)
    return headings


def find_pieces(full: str) -> list[Piece]:
    """Cut the act's text into recitals, articles and annexes."""
    # "HAVE ADOPTED THIS REGULATION:" separates the recitals from the articles.
    # Some old scans lack a readable one; then the articles start at Article 1.
    adopted = ADOPTED.search(full)
    articles = article_headings(full, adopted.end() if adopted else 0)
    if not articles:
        return [Piece("body", "", full, 0)]
    preamble_end = adopted.start() if adopted else articles[0].start()

    # Annexes start at the first ANNEX heading after the last article (one
    # before it is a table of contents).
    annex = ANNEX.search(full, articles[-1].end())
    annex_start = annex.start() if annex else len(full)
    divisions = find_divisions(full[:annex_start])

    pieces = [Piece("preamble", "", full[:preamble_end], 0)]
    for i, match in enumerate(articles):
        end = articles[i + 1].start() if i + 1 < len(articles) else annex_start
        body = drop_division_lines(full[match.end() : end].strip("\n"))
        title, body = heading_title(body)
        label = f"Article {match.group(1)}" + (f" {title}" if title else "")
        division = division_at(divisions, match.start())
        if division:
            label = f"{division} | {label}"
        pieces.append(Piece("article", label, body.strip(), match.start()))

    if annex:
        annexes = list(ANNEX.finditer(full, annex_start))
        for i, match in enumerate(annexes):
            end = annexes[i + 1].start() if i + 1 < len(annexes) else len(full)
            body = full[match.end() : end].strip("\n")
            title, body = heading_title(body)
            label = match.group(0).strip().title() + (f" {title}" if title else "")
            pieces.append(Piece("annex", label, body.strip(), match.start()))
    return pieces


# --- Sizing ------------------------------------------------------------------


def pack(units: list[str], fits) -> list[str]:
    """Join neighbouring units (recitals, paragraphs) while the result fits."""
    groups = []
    current = ""
    for unit in units:
        candidate = f"{current}\n{unit}" if current else unit
        if fits(candidate):
            current = candidate
        else:
            if current:
                groups.append(current)
            current = unit
    if current:
        groups.append(current)
    return groups


def split_to_fit(text: str, units_at: re.Pattern | None, fits) -> list[str]:
    """Pieces of text that each fit: first at natural boundaries (recitals,
    paragraphs), then, for anything still too long, by size."""
    if fits(text):
        return [text]
    units = units_at.split(text) if units_at else [text]
    pieces = []
    for group in pack(units, fits):
        if fits(group):
            pieces.append(group)
            continue
        size = max(len(group) // 2, 400)
        while True:
            parts = RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=0).split_text(group)
            if all(fits(p) for p in parts) or size <= 400:
                break
            size = int(size * 0.75)
        pieces += parts
    return pieces


def structure_chunks(title: str, pages: list[tuple[int, str]], count_tokens, max_tokens: int) -> list[dict]:
    """The act's chunks: header + text, with section, label and page range."""
    starts = []
    texts = []
    offset = 0
    for number, text in pages:
        starts.append((offset, number))
        texts.append(text)
        offset += len(text) + 1
    full = "\n".join(texts)

    def page_at(position: int) -> int:
        number = starts[0][1]
        for start, page_number in starts:
            if start > position:
                break
            number = page_number
        return number

    act = (title or "").strip()
    if len(act) > TITLE_CHARS:
        act = act[:TITLE_CHARS].rsplit(" ", 1)[0] + "..."

    chunks = []
    for piece in find_pieces(full):
        if not piece.text.strip():
            continue
        if piece.section == "preamble":
            label = "Preamble and recitals"
            units_at = RECITAL_START
        elif piece.section == "article":
            label = piece.label
            units_at = PARAGRAPH_START
        else:
            label = piece.label
            units_at = None
        header = f"{act} | {label}" if label else act

        def fits(text: str, header=header) -> bool:
            return count_tokens(f"{header}\n{text}") <= max_tokens

        for part in split_to_fit(piece.text, units_at, fits):
            position = full.find(part[:80], piece.start)
            position = piece.start if position < 0 else position
            chunks.append(
                {
                    "section": piece.section,
                    "label": label,
                    "text": f"{header}\n{part}",
                    "page_start": page_at(position),
                    "page_end": page_at(position + len(part)),
                }
            )
    return chunks
