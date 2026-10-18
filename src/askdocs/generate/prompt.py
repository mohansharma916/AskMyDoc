from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..retrieve.types import Candidate

NOT_FOUND = "NOT_FOUND"
# Opens a sentence naming a part of the question the excerpts don't cover; it needs no citation.
NOT_COVERED = "The documents do not say"


@dataclass(frozen=True)
class PromptTemplate:
    version: str
    system: str


@lru_cache
def load_prompt(prompts_dir: Path, version: str) -> PromptTemplate:
    path = prompts_dir / f"{version}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt '{version}' not found at {path}")
    return PromptTemplate(version, path.read_text(encoding="utf-8").strip())


def format_excerpt(n: int, c: Candidate) -> str:
    source = c.file_name or c.doc_id
    if c.page:
        source += f", page {c.page}"
    if c.section:
        source += f", section: {c.section}"
    return f"[{n}] ({source})\n{c.text}"


def build_user_message(question: str, chunks: list[Candidate]) -> str:
    excerpts = "\n\n".join(format_excerpt(n, c) for n, c in enumerate(chunks, start=1))
    return f"Excerpts:\n\n{excerpts}\n\nQuestion: {question}"


def build_retry_message(issues: list[str], n_chunks: int) -> str:
    listed = "\n".join(f"- {issue}" for issue in issues)
    return (
        f"Your previous answer broke the citation rules:\n{listed}\n\n"
        f"Rewrite it so every sentence ends with citations to excerpts [1] to [{n_chunks}], "
        f'except sentences starting "{NOT_COVERED}" for parts the excerpts do not cover. '
        f"Reply with exactly {NOT_FOUND} if the excerpts support no part of the question."
    )
