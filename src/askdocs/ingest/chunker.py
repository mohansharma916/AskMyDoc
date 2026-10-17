"""Structure-aware chunking: split by section first, then pack whole sentences.

Chunks never cross a section boundary and never split a sentence, except a
single sentence longer than the chunk size, which is cut by tokens as a last
resort. Consecutive chunks of a section share up to ``overlap`` tokens of
trailing sentences.
"""

import re
from dataclasses import dataclass
from functools import lru_cache
from itertools import groupby

import tiktoken

from .parsers import Block

# Split after . ! ? when the next sentence starts with a capital, digit, quote or bracket.
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]?\s+(?=[A-Z0-9\"'(\[])")


@lru_cache
def _encoding():
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoding().encode(text))


@dataclass(frozen=True)
class TextChunk:
    text: str
    page: int | None
    section_path: tuple[str, ...]
    token_count: int
    position: int


@dataclass(frozen=True)
class _Unit:
    text: str
    page: int | None
    tokens: int
    starts_block: bool


def split_sentences(text: str) -> list[str]:
    if "\n" in text or text.count(" | "):  # code and table rows stay whole
        return [text]
    return [s for s in _SENTENCE_END.split(text) if s.strip()]


def _units(blocks: list[Block], max_tokens: int) -> list[_Unit]:
    units = []
    for block in blocks:
        for i, sentence in enumerate(split_sentences(block.text)):
            tokens = count_tokens(sentence)
            if tokens <= max_tokens:
                units.append(_Unit(sentence, block.page, tokens, i == 0))
                continue
            ids = _encoding().encode(sentence)  # oversize sentence: cut by tokens
            for j in range(0, len(ids), max_tokens):
                piece = _encoding().decode(ids[j : j + max_tokens])
                units.append(_Unit(piece, block.page, len(ids[j : j + max_tokens]), i == 0 and j == 0))
    return units


def _join(units: list[_Unit]) -> str:
    out = ""
    for i, unit in enumerate(units):
        if i:
            out += "\n" if unit.starts_block else " "
        out += unit.text
    return out


def chunk_blocks(blocks: list[Block], chunk_size: int = 512, overlap: int = 64) -> list[TextChunk]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[TextChunk] = []
    for section_path, group in groupby(blocks, key=lambda b: b.section_path):
        units = _units(list(group), chunk_size)
        current: list[_Unit] = []
        size = 0

        def emit(units_: list[_Unit], section_path=section_path) -> None:
            text = _join(units_)
            chunks.append(TextChunk(text, units_[0].page, section_path, count_tokens(text), len(chunks)))

        for unit in units:
            if current and size + unit.tokens + 1 > chunk_size:
                emit(current)
                # Carry trailing whole sentences (up to `overlap` tokens) into the next chunk.
                carry: list[_Unit] = []
                carried = 0
                for prev in reversed(current):
                    if carried + prev.tokens > overlap:
                        break
                    carry.insert(0, prev)
                    carried += prev.tokens
                if carried + unit.tokens + 1 > chunk_size:
                    carry, carried = [], 0
                current, size = carry, carried
            current.append(unit)
            size += unit.tokens + 1
        if current:
            emit(current)
    return chunks

