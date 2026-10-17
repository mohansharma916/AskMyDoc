import io
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from . import vectorstore
from .config import get_settings

SUPPORTED_EXTENSIONS = {".pdf", ".md", ".markdown", ".txt"}


def _splitter() -> RecursiveCharacterTextSplitter:
    s = get_settings()
    # Token-based sizing (tiktoken) so chunk_size/overlap are measured in tokens.
    return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base", chunk_size=s.chunk_size, chunk_overlap=s.chunk_overlap
    )


def _extract_pages(filename: str, data: bytes) -> list[tuple[int | None, str]]:
    """Return (page_number, text) pairs. Non-PDF files are a single page=None entry."""
    if Path(filename).suffix.lower() == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        return [(i, page.extract_text() or "") for i, page in enumerate(reader.pages, start=1)]
    return [(None, data.decode("utf-8", errors="replace"))]


def ingest_file(filename: str, data: bytes) -> dict:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type '{suffix}'. Use: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")

    splitter = _splitter()
    chunks: list[dict] = []
    for page, text in _extract_pages(filename, data):
        for piece in splitter.split_text(text):
            if piece.strip():
                chunks.append({"text": piece, "source": filename, "page": page, "chunk_index": len(chunks)})

    if not chunks:
        raise ValueError(f"No extractable text found in '{filename}'")

    # Re-uploading a file replaces its previous chunks instead of duplicating them.
    vectorstore.delete_source(filename)
    vectorstore.add_chunks(chunks)
    return {"source": filename, "chunks": len(chunks)}
