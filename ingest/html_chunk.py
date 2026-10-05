"""Chunk an act from its EUR-Lex HTML instead of its PDF.

Two kinds of HTML (see download_html.py):

- Tagged XHTML (most acts since the 2000s): every part has an id, so the
  structure is read, not guessed. rct_85 is recital 85, art_33 is Article 33,
  cpt_IV.sct_2 is Chapter IV Section 2, 033.001 is its paragraph 1, anx_I is
  Annex I, fnp_1 a footnote.
- Plain HTML (older acts): clean typed text, one paragraph per <p>. It has no
  ids, but "HAS ADOPTED THIS REGULATION" and "Article N" sit on lines of their
  own, so the rules in structure.py find the parts.

Each chunk starts with a header naming the act and the part:
"Regulation (EU) 2016/679 ... | CHAPTER IV Controller and processor |
Section 2 Security of personal data | Article 33 Notification of a personal
data breach to the supervisory authority".

Compared with the PDF chunker, recitals are packed in smaller groups (they
read like summaries and crowded out articles), tiny pieces such as
"This Regulation shall enter into force..." join the chunk before them, and
annex pieces that are mostly numbers (tariff and budget tables) are dropped.
"""

import re

import lxml.html
from structure import (
    PARAGRAPH_START,
    RECITAL_START,
    TITLE_CHARS,
    find_pieces,
    split_to_fit,
)

RECITAL_TOKENS = 250  # recitals per chunk: a few, not a page of them
SMALL_CHARS = 200  # pieces shorter than this join the chunk before them
ARTICLE_ID = re.compile(r"^art_[0-9]+[a-z]*$")
ANNEX_ID = re.compile(r"^anx_[^.]+$")
RECITAL_ID = re.compile(r"^rct_(\d+)$")
DIVISION_ID = re.compile(r"(?:^|\.)(cpt|tis|prt|sct|sbs)_[^.]+$")
NEWLINE = re.compile(r"\n")
SPACES = re.compile(r"[ \t ]+")


# --- Text from HTML elements ---------------------------------------------------


def clean_line(text: str) -> str:
    return SPACES.sub(" ", text).strip()


def is_list_row(row) -> bool:
    """A list point laid out as a table row: "(a)" in one cell, its text in the
    next, at most one paragraph per cell. (Some old pages put the whole act
    in one big table cell; that row is not a list point.)"""
    cells = row.findall("td")
    return 0 < len(cells) <= 3 and all(len(td.findall(".//p")) <= 1 for td in cells)


def text_of(element) -> str:
    """The element's text, one line per paragraph; a list point is one line."""
    lines = []
    rows_done = set()
    for node in element.iter("p", "tr"):
        if node.tag == "tr":
            if is_list_row(node):
                cells = [clean_line(td.text_content()) for td in node.findall("td")]
                line = " ".join(c for c in cells if c)
                if line:
                    lines.append(line)
                rows_done.add(node)
            continue
        if any(a in rows_done for a in node.iterancestors("tr")):
            continue  # already part of its list row
        if node.find(".//p") is not None:
            # An unclosed <p> on an old page wraps the paragraphs after it:
            # take only its own text, the inner ones come next anyway.
            line = clean_line(node.text or "")
        else:
            line = clean_line(node.text_content())
        if line:
            lines.append(line)
    return "\n".join(lines)


def parse(html: bytes):
    """The page as a tree. EUR-Lex pages are UTF-8; letting the parser guess
    turns "GRÉGOIRE" into "GRÃGOIRE"."""
    text = html.decode("utf-8", errors="replace")
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text)  # lxml refuses str input with an XML declaration
    # Old pages break lines with <br> inside one <p>; keep those breaks, or
    # "Whereas" and "HAS ADOPTED" stop starting lines of their own.
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    return lxml.html.fromstring(text)


def first_text(element, css_class: str) -> str:
    """Text of the first <p> with this class inside the element, or ''."""
    for p in element.iter("p"):
        if css_class in (p.get("class") or "").split():
            return clean_line(p.text_content())
    return ""


def is_mostly_numbers(text: str) -> bool:
    """A table of figures: more digits than letters."""
    letters = sum(c.isalpha() for c in text)
    digits = sum(c.isdigit() for c in text)
    return digits > letters


# --- Tagged XHTML -----------------------------------------------------------------


def division_label(article) -> str:
    """'CHAPTER IV Controller and processor | Section 2 Security of ...' from
    the article's enclosing divisions (their ids end in cpt_/tis_/prt_/sct_)."""
    parts = []
    for ancestor in article.iterancestors("div"):
        division_id = ancestor.get("id") or ""
        if DIVISION_ID.search(division_id):
            heading = ""
            title = ""
            for child in ancestor:
                child_id = child.get("id") or ""
                if child.tag == "p" and not heading:
                    heading = clean_line(child.text_content())
                if child_id == f"{division_id}.tit_1":
                    title = clean_line(child.text_content())
                    break
            parts.append(f"{heading} {title}".strip() if title != heading else title)
    return " | ".join(reversed([p for p in parts if p]))


def article_pieces(article) -> tuple[str, list[str]]:
    """An article's label and its paragraphs (or its whole text, when it has
    no numbered paragraphs)."""
    number = first_text(article, "oj-ti-art")
    title = first_text(article, "oj-sti-art")
    label = f"{number} {title}".strip() if title else number
    paragraphs = []
    for child in article.iter("div"):
        if re.match(r"^\d{3}\.\d{3}$", child.get("id") or ""):
            paragraphs.append(text_of(child))
    if not paragraphs:
        body = text_of(article)
        # Drop the heading lines repeated at the top of the body.
        lines = body.split("\n")
        while lines and lines[0] in (number, title):
            lines = lines[1:]
        paragraphs = ["\n".join(lines)]
    return label, [p for p in paragraphs if p]


def tagged_pieces(root) -> list[dict]:
    """Recitals, articles and annexes of a tagged XHTML act, in order."""
    pieces = []
    for element in root.iter("div"):
        element_id = element.get("id") or ""
        if RECITAL_ID.match(element_id):
            pieces.append({"section": "preamble", "label": "Recitals", "units": [text_of(element)]})
        elif ARTICLE_ID.match(element_id):
            label, paragraphs = article_pieces(element)
            division = division_label(element)
            if division:
                label = f"{division} | {label}"
            pieces.append({"section": "article", "label": label, "units": paragraphs})
        elif ANNEX_ID.match(element_id):
            lines = text_of(element).split("\n")
            heading = lines[0] if lines else "Annex"
            # The annex title is usually the next short line.
            title = lines[1] if len(lines) > 1 and len(lines[1]) <= 120 else ""
            body = lines[2:] if title else lines[1:]
            pieces.append({"section": "annex", "label": f"{heading} {title}".strip(), "units": body})
    return pieces


# --- Plain HTML ------------------------------------------------------------------


def plain_pieces(root) -> list[dict]:
    """Recitals, articles and annexes of a plain-HTML act, found with the same
    rules as the PDF chunker, but on clean text."""
    container = root.get_element_by_id("TexteOnly", None)
    text = text_of(container if container is not None else root)
    pieces = []
    for piece in find_pieces(text):
        if piece.section == "preamble":
            units = RECITAL_START.split(piece.text)
            pieces.append({"section": "preamble", "label": "Recitals", "units": units})
        elif piece.section == "article":
            pieces.append({"section": "article", "label": piece.label, "units": PARAGRAPH_START.split(piece.text)})
        else:
            pieces.append({"section": piece.section, "label": piece.label, "units": piece.text.split("\n")})
    return pieces


# --- From pieces to chunks ----------------------------------------------------------


def html_chunks(html: bytes, title: str, count_tokens, max_tokens: int) -> list[dict]:
    """The act's chunks: header + text, with section and label."""
    root = parse(html)
    tagged = root.find(".//div[@class='eli-container']") is not None
    pieces = tagged_pieces(root) if tagged else plain_pieces(root)

    act = clean_line(title or "")
    if len(act) > TITLE_CHARS:
        act = act[:TITLE_CHARS].rsplit(" ", 1)[0] + "..."

    chunks = []
    for piece in pieces:
        units = [u.strip() for u in piece["units"] if u and u.strip()]
        if not units:
            continue
        header = f"{act} | {piece['label']}" if piece["label"] else act
        budget = RECITAL_TOKENS if piece["section"] == "preamble" else max_tokens

        def fits(text: str, header=header, budget=budget) -> bool:
            return count_tokens(f"{header}\n{text}") <= budget

        units_at = PARAGRAPH_START if piece["section"] == "article" else NEWLINE
        for part in split_to_fit("\n".join(units), units_at, fits):
            if piece["section"] == "annex" and is_mostly_numbers(part):
                continue  # tables of figures match no question
            chunks.append({"section": piece["section"], "label": piece["label"], "header": header, "body": part})

    chunks = merge_recitals(chunks, count_tokens)
    chunks = merge_small(chunks, count_tokens, max_tokens)
    for chunk in chunks:
        chunk["text"] = f"{chunk['header']}\n{chunk['body']}"
        chunk["page_start"] = chunk["page_end"] = 0  # HTML has no pages
        del chunk["header"], chunk["body"]
    return chunks


def merge_recitals(chunks: list[dict], count_tokens) -> list[dict]:
    """Recitals come one per piece; join neighbours up to RECITAL_TOKENS and
    name the range, e.g. "Recitals (85)-(86)"."""
    merged = []
    for chunk in chunks:
        previous = merged[-1] if merged else None
        if (
            chunk["section"] == "preamble"
            and previous is not None
            and previous["section"] == "preamble"
            and count_tokens(f"{previous['header']}\n{previous['body']}\n{chunk['body']}") <= RECITAL_TOKENS
        ):
            previous["body"] += "\n" + chunk["body"]
        else:
            merged.append(dict(chunk))
    for chunk in merged:
        if chunk["section"] == "preamble":
            numbers = re.findall(r"^\((\d+)\)", chunk["body"], re.MULTILINE)
            if numbers:
                label = f"Recitals ({numbers[0]})" + (f"-({numbers[-1]})" if len(numbers) > 1 else "")
                chunk["header"] = chunk["header"].rsplit(" | ", 1)[0] + f" | {label}"
                chunk["label"] = label
    return merged


def merge_small(chunks: list[dict], count_tokens, max_tokens: int) -> list[dict]:
    """A piece under SMALL_CHARS ("This Regulation shall enter into force...")
    joins the chunk before it, with its own label inside the text."""
    merged = []
    for chunk in chunks:
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and previous["section"] == chunk["section"]
            and len(chunk["body"]) < SMALL_CHARS
            and count_tokens(f"{previous['header']}\n{previous['body']}\n{chunk['label']}: {chunk['body']}") <= max_tokens
        ):
            previous["body"] += f"\n{chunk['label'].split(' | ')[-1]}: {chunk['body']}"
        else:
            merged.append(chunk)
    return merged
