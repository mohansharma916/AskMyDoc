# Ask My Docs

A production-style RAG system for one document collection: hybrid retrieval (BM25 + vectors), cross-encoder reranking, enforced citations, and a CI-gated evaluation pipeline.

> Work in progress. Setup instructions arrive with the API and UI.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
ruff check . && pytest
```
