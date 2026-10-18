"""Post-generation citation checks.

An answer passes when every factual sentence carries at least one [n] marker
and every marker points at one of the excerpts that were shown to the model.
Sentences starting with NOT_COVERED name what the excerpts don't say, so they
need no citation; an answer made only of them counts as not found.
"""

import re
from dataclasses import dataclass, field

from .prompt import NOT_COVERED, NOT_FOUND

_CITATION = re.compile(r"\[(\d+)\]")
# Split after sentence punctuation (optionally followed by citations), before the next sentence.
_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(*])|(?<=\])\s+(?=[A-Z0-9\"'(*])")
_LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def cited_numbers(text: str) -> list[int]:
    return [int(n) for n in _CITATION.findall(text)]


def is_gap(sentence: str) -> bool:
    return sentence.strip().strip("*`").lower().startswith(NOT_COVERED.lower())


def is_not_found(answer: str) -> bool:
    text = answer.strip().strip("*`")
    return text.upper().startswith(NOT_FOUND) or (is_gap(text) and not cited_numbers(text))


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
            if len(words) >= 3 and not is_gap(sentence):
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
        if not self.ok and not issues:
            issues.append("The answer has no complete, cited sentence.")
        return issues


def check_citations(answer: str, n_chunks: int) -> CitationCheck:
    sentences = answer_sentences(answer)
    uncited = [s for s in sentences if not _CITATION.search(s)]
    out_of_range = [n for n in cited_numbers(answer) if not 1 <= n <= n_chunks]
    ok = bool(sentences) and not uncited and not out_of_range
    return CitationCheck(ok, uncited, out_of_range)
