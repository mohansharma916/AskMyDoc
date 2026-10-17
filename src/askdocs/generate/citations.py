"""Post-generation citation checks.

An answer passes when every factual sentence carries at least one [n] marker
and every marker points at one of the excerpts that were shown to the model.
"""

import re
from dataclasses import dataclass, field

from .prompt import NOT_FOUND

_CITATION = re.compile(r"\[(\d+)\]")
# Split after sentence punctuation (optionally followed by citations), before the next sentence.
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(*])|(?<=\])\s+(?=[A-Z0-9\"'(*])")
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def cited_numbers(text: str) -> list[int]:
    return [int(n) for n in _CITATION.findall(text)]


def is_not_found(answer: str) -> bool:
    return answer.strip().strip("*`").upper().startswith(NOT_FOUND)


def answer_sentences(answer: str) -> list[str]:
    """Sentences that must carry citations: skips headings, lead-in lines and tiny fragments."""
    sentences = []
    for line in answer.splitlines():
        line = _LIST_MARKER.sub("", line).strip()
        if not line or line.startswith("#") or line.endswith(":"):
            continue
        for sentence in _SENTENCE_BREAK.split(line):
            sentence = sentence.strip()
            words = _CITATION.sub("", sentence).split()
            if len(words) >= 3:
                sentences.append(sentence)
    return sentences


@dataclass
class CitationCheck:
    ok: bool
    uncited: list[str] = field(default_factory=list)
    out_of_range: list[int] = field(default_factory=list)

    @property
    def issues(self) -> list[str]:
        issues = [f"Sentence without a citation: {s!r}" for s in self.uncited]
        if self.out_of_range:
            issues.append(f"Citations to excerpts that do not exist: {sorted(set(self.out_of_range))}")
        return issues


def check_citations(answer: str, n_chunks: int) -> CitationCheck:
    sentences = answer_sentences(answer)
    uncited = [s for s in sentences if not _CITATION.search(s)]
    out_of_range = [n for n in cited_numbers(answer) if not 1 <= n <= n_chunks]
    ok = bool(sentences) and not uncited and not out_of_range
    return CitationCheck(ok, uncited, out_of_range)
