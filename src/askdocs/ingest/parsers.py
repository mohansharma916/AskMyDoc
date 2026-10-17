"""Turn files into text blocks that remember their page and heading path.

Every parser returns a ``ParsedDocument``: a title plus an ordered list of
``Block``s. The chunker groups blocks by ``section_path`` so chunks never
straddle two sections.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".html", ".htm", ".txt"}


@dataclass(frozen=True)
class Block:
    text: str
    page: int | None = None
    section_path: tuple[str, ...] = ()


@dataclass
class ParsedDocument:
    title: str
    blocks: list[Block] = field(default_factory=list)


class UnsupportedFileType(ValueError):
    pass


# --- Normalisation ---------------------------------------------------------

_SPACES = re.compile(r"[ \t ]+")


def normalize(text: str, keep_newlines: bool = False) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if keep_newlines:
        lines = [line.replace("\t", "    ").rstrip() for line in text.split("\n")]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip("\n")
    return _SPACES.sub(" ", text.replace("\n", " ")).strip()


class _HeadingStack:
    """Tracks the current heading hierarchy as headings of various levels arrive."""

    def __init__(self):
        self._stack: list[tuple[int, str]] = []

    def push(self, level: int, title: str) -> None:
        while self._stack and self._stack[-1][0] >= level:
            self._stack.pop()
        self._stack.append((level, title))

    @property
    def path(self) -> tuple[str, ...]:
        return tuple(title for _, title in self._stack)


# --- Markdown ----------------------------------------------------------------


def parse_markdown(text: str, fallback_title: str) -> ParsedDocument:
    tokens = MarkdownIt("commonmark").enable("table").parse(text)
    headings = _HeadingStack()
    blocks: list[Block] = []
    title: str | None = None
    list_depth = 0
    row: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            heading = normalize(tokens[i + 1].content)
            level = int(tok.tag[1])
            if level == 1 and title is None:
                title = heading
            headings.push(level, heading)
            i += 3
            continue
        if tok.type in ("bullet_list_open", "ordered_list_open"):
            list_depth += 1
        elif tok.type in ("bullet_list_close", "ordered_list_close"):
            list_depth -= 1
        elif tok.type == "inline" and tokens[i - 1].type == "paragraph_open":
            content = normalize(tok.content)
            if content:
                prefix = "  " * (list_depth - 1) + "- " if list_depth else ""
                blocks.append(Block(prefix + content, None, headings.path))
        elif tok.type in ("fence", "code_block"):
            code = normalize(tok.content, keep_newlines=True)
            if code:
                blocks.append(Block(code, None, headings.path))
        elif tok.type == "tr_open":
            row = []
        elif tok.type == "inline" and tokens[i - 1].type in ("th_open", "td_open"):
            row.append(normalize(tok.content))
        elif tok.type == "tr_close" and any(row):
            blocks.append(Block(" | ".join(row), None, headings.path))
        i += 1
    return ParsedDocument(title or fallback_title, blocks)


# --- HTML --------------------------------------------------------------------

_HTML_BLOCKS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "pre", "tr", "blockquote", "dt", "dd"]
_HTML_NOISE = ["script", "style", "noscript", "nav", "footer", "template", "svg"]


def parse_html(html: str, fallback_title: str) -> ParsedDocument:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_HTML_NOISE):
        tag.decompose()

    title = normalize(soup.title.get_text()) if soup.title else ""
    root = soup.body or soup
    headings = _HeadingStack()
    blocks: list[Block] = []
    block_names = set(_HTML_BLOCKS)

    for el in root.find_all(_HTML_BLOCKS):
        if el.name[0] == "h" and el.name[1:].isdigit():
            heading = normalize(el.get_text(" "))
            if heading:
                title = title or heading
                headings.push(int(el.name[1]), heading)
            continue
        # Skip blocks nested in another block (e.g. <p> inside <li>) to avoid duplicates.
        if any(parent.name in block_names for parent in el.parents):
            continue
        if el.name == "pre":
            text = normalize(el.get_text(), keep_newlines=True)
        elif el.name == "tr":
            text = " | ".join(normalize(c.get_text(" ")) for c in el.find_all(["th", "td"]))
        else:
            text = normalize(el.get_text(" "))
            if el.name == "li":
                text = "- " + text
        if text.strip(" |-"):
            blocks.append(Block(text, None, headings.path))

    if not blocks:  # pages built from bare <div>s
        blocks = [Block(p, None, ()) for p in _paragraphs(root.get_text("\n"))]
    return ParsedDocument(title or fallback_title, blocks)


# --- Plain text --------------------------------------------------------------


def _paragraphs(text: str) -> list[str]:
    return [p for p in (normalize(part) for part in re.split(r"\n\s*\n", text)) if p]


def parse_text(text: str, fallback_title: str) -> ParsedDocument:
    return ParsedDocument(fallback_title, [Block(p) for p in _paragraphs(text)])


# --- Dispatch ----------------------------------------------------------------


def title_from_filename(file_name: str) -> str:
    return re.sub(r"[_\-]+", " ", Path(file_name).stem).strip().title()


def parse_bytes(file_name: str, data: bytes) -> ParsedDocument:
    suffix = Path(file_name).suffix.lower()
    fallback = title_from_filename(file_name)
    if suffix == ".pdf":
        from .pdf import parse_pdf  # PyMuPDF is only needed for PDFs

        return parse_pdf(data, fallback)
    if suffix not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileType(
            f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    text = data.decode("utf-8", errors="replace")
    if suffix in (".md", ".markdown"):
        return parse_markdown(text, fallback)
    if suffix in (".html", ".htm"):
        return parse_html(text, fallback)
    return parse_text(text, fallback)


def parse_file(path: Path) -> ParsedDocument:
    return parse_bytes(path.name, path.read_bytes())
