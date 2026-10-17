"""Build eval/golden.jsonl from eval/golden_source.yaml.

Evidence quotes are mapped to the ids of the corpus chunks that contain them,
using the same parser, chunker and id scheme as ingestion. Re-run after
changing the corpus or chunking settings:

    python -m eval.build_golden
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import yaml

from askdocs.config import get_settings
from askdocs.ingest.chunker import chunk_blocks
from askdocs.ingest.indexer import make_chunk_id, slugify
from askdocs.ingest.parsers import SUPPORTED_EXTENSIONS, normalize, parse_bytes

EVAL_DIR = Path(__file__).parent
CORPUS = EVAL_DIR / "corpus"
SOURCE = EVAL_DIR / "golden_source.yaml"
GOLDEN = EVAL_DIR / "golden.jsonl"


def corpus_chunks(corpus: Path = CORPUS, chunk_size: int | None = None, overlap: int | None = None):
    """(chunk_id, text) for every corpus chunk, exactly as the indexer would create them."""
    s = get_settings()
    out = []
    for path in sorted(p for p in corpus.iterdir() if p.suffix.lower() in SUPPORTED_EXTENSIONS):
        data = path.read_bytes()
        doc_id, content_hash = slugify(path.stem), hashlib.sha256(data).hexdigest()
        chunks = chunk_blocks(
            parse_bytes(path.name, data).blocks, chunk_size or s.chunk_size, overlap or s.chunk_overlap
        )
        out += [(make_chunk_id(doc_id, content_hash, c.position), normalize(c.text)) for c in chunks]
    return out


def build(source: Path = SOURCE, corpus: Path = CORPUS) -> list[dict]:
    chunks = corpus_chunks(corpus)
    items = []
    for raw in yaml.safe_load(source.read_text()):
        answerable = raw.get("answerable", True)
        evidence = []
        for quote in raw.get("evidence", []):
            ids = [cid for cid, text in chunks if normalize(quote) in text]
            if not ids:
                raise ValueError(f"{raw['id']}: evidence not found in corpus: {quote!r}")
            evidence.append({"quote": quote, "chunk_ids": ids})
        if answerable and not evidence:
            raise ValueError(f"{raw['id']}: answerable items need evidence")
        items.append(
            {
                "id": raw["id"],
                "question": raw["question"],
                "expected_answer": raw.get("expected_answer", "NOT_FOUND"),
                "supporting_chunk_ids": list(dict.fromkeys(cid for e in evidence for cid in e["chunk_ids"])),
                "evidence": evidence,
                "answerable": answerable,
                "tags": raw.get("tags", []),
            }
        )
    return items


def to_jsonl(items: list[dict]) -> str:
    return "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)


def load_golden(path: Path = GOLDEN) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if golden.jsonl is out of date")
    args = parser.parse_args(argv)
    content = to_jsonl(build())
    if args.check:
        if not GOLDEN.exists() or GOLDEN.read_text() != content:
            print("eval/golden.jsonl is out of date; run python -m eval.build_golden", file=sys.stderr)
            return 1
        print("eval/golden.jsonl is up to date")
        return 0
    GOLDEN.write_text(content)
    items = load_golden()
    answerable = sum(i["answerable"] for i in items)
    print(f"Wrote {len(items)} items to {GOLDEN} ({answerable} answerable, {len(items) - answerable} unanswerable)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
