"""PDF parsing with PyMuPDF: per-page text, font-size headings, header/footer removal."""

import re
from collections import Counter

import pymupdf

from .parsers import Block, ParsedDocument, _HeadingStack, normalize

HEADING_SIZE_RATIO = 1.15  # a line this much larger than body text is a heading
MAX_HEADING_CHARS = 120
REPEAT_PAGE_FRACTION = 0.5  # lines on at least this share of pages are headers/footers


def _line_text(line: dict) -> str:
    return "".join(span["text"] for span in line["spans"])


def _line_size(line: dict) -> float:
    sizes = [span["size"] for span in line["spans"] if span["text"].strip()]
    return round(max(sizes), 1) if sizes else 0.0


def _repeat_key(text: str) -> str:
    """Page numbers differ per page, so compare lines with digits masked."""
    return re.sub(r"\d+", "#", normalize(text).lower())


def _page_lines(page) -> list[list[dict]]:
    """Text blocks of a page as lists of non-empty lines, in reading order."""
    blocks = page.get_text("dict", sort=True)["blocks"]
    result = []
    for block in blocks:
        if block.get("type") != 0:  # skip images
            continue
        lines = [ln for ln in block["lines"] if _line_text(ln).strip()]
        if lines:
            result.append(lines)
    return result


def _repeated_lines(pages: list[list[list[dict]]]) -> set[str]:
    if len(pages) < 3:
        return set()
    seen: Counter[str] = Counter()
    for blocks in pages:
        # Only the first and last two lines of a page can be running headers/footers.
        lines = [ln for block in blocks for ln in block]
        edge = lines[:2] + lines[-2:]
        seen.update({_repeat_key(_line_text(ln)) for ln in edge})
    threshold = max(2, int(len(pages) * REPEAT_PAGE_FRACTION))
    return {key for key, count in seen.items() if count >= threshold and key.strip("# ")}


def parse_pdf(data: bytes, fallback_title: str) -> ParsedDocument:
    with pymupdf.open(stream=data, filetype="pdf") as pdf:
        meta_title = normalize((pdf.metadata or {}).get("title") or "")
        pages = [_page_lines(page) for page in pdf]

    repeated = _repeated_lines(pages)

    # Body size = the font size carrying the most characters.
    size_chars: Counter[float] = Counter()
    for blocks in pages:
        for block in blocks:
            for ln in block:
                size_chars[_line_size(ln)] += len(_line_text(ln))
    body_size = size_chars.most_common(1)[0][0] if size_chars else 0.0
    heading_sizes = sorted(
        {s for s in size_chars if body_size and s >= body_size * HEADING_SIZE_RATIO}, reverse=True
    )
    level_of = {size: i + 1 for i, size in enumerate(heading_sizes)}

    headings = _HeadingStack()
    title = meta_title
    out: list[Block] = []
    for page_no, blocks in enumerate(pages, start=1):
        for block in blocks:
            paragraph: list[str] = []

            def flush(page_no=page_no, paragraph=paragraph):
                text = normalize(re.sub(r"-\s*\n\s*", "", "\n".join(paragraph)))
                if text:
                    out.append(Block(text, page_no, headings.path))
                paragraph.clear()

            for ln in block:
                text = _line_text(ln)
                if _repeat_key(text) in repeated:
                    continue
                size = _line_size(ln)
                if size in level_of and len(text.strip()) <= MAX_HEADING_CHARS:
                    flush()
                    heading = normalize(text)
                    if level_of[size] == 1 and not title:
                        title = heading
                    headings.push(level_of[size], heading)
                else:
                    paragraph.append(text)
            flush()

    return ParsedDocument(title or fallback_title, out)
