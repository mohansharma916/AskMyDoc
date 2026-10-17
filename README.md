# Ask My Docs

A production-style RAG system for one document collection: hybrid retrieval (BM25 + vectors), cross-encoder reranking, enforced citations, and a CI-gated evaluation pipeline.

See [Architecture.md](Architecture.md) for the design and [Decision.md](Decision.md) for the decision records.

> Work in progress. Ingestion is complete; retrieval, generation, the API and the UI are next.

## Setup

Prerequisites: Python 3.11+ and Docker.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
docker compose up -d qdrant
```

## Ingest documents

```bash
python -m askdocs.ingest --path eval/corpus     # or any folder of PDF / Markdown / HTML / TXT files
```

Re-running the command skips unchanged files. A file whose content has changed has its old chunks replaced.

## Development

```bash
ruff check . && ruff format --check .
pytest
```
