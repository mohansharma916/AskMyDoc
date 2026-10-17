# Ask My Docs

A production-style RAG system for one document collection. It combines hybrid retrieval (BM25 + vectors fused with RRF), cross-encoder reranking, enforced citations, and abstention when the documents don't cover a question.

See [Architecture.md](Architecture.md) for the design and [Decision.md](Decision.md) for the decision records.

> Work in progress. Ingestion, retrieval, generation and the REST API are done; the eval CI gate and the web UI are next.

## Setup

Prerequisites: Python 3.11+, Docker, and an Anthropic API key (or a local [Ollama](https://ollama.com) model).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env          # set LLM_API_KEY
docker compose up -d qdrant
python -m askdocs.ingest --path eval/corpus
uvicorn askdocs.api.main:app --reload
```

The OpenAPI docs are at http://localhost:8000/docs. If port 8000 is taken, pass `--port 8001` and use that port everywhere below.

To use a local model instead, set `LLM_PROVIDER=ollama` and `LLM_MODEL=llama3.1` (any model you've pulled).

## API

All endpoints are under `/api/v1`, with JSON in and out.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/ingest` | Upload `files`, or give a `path` under `INGEST_ROOT`; returns a background job |
| GET | `/ingest/{job_id}` | Job status and counts |
| POST | `/ask` | Cited answer with usage and per-stage latency |
| POST | `/ask/stream` | The same answer streamed as server-sent events: `meta`, `token`, `retry`, `done` (or `error`) |
| GET | `/documents` | List indexed documents |
| DELETE | `/documents/{doc_id}` | Remove a document and its chunks |
| GET | `/health` | Database, Qdrant and LLM configuration checks |

```bash
curl -s localhost:8000/api/v1/ask -H 'content-type: application/json' \
  -d '{"question": "How long is parental leave for primary caregivers?", "top_k": 5}'
```

Errors share one shape, `{"error": {"code", "message", "trace_id"}}`, with these codes:

| Status | Code |
|--------|------|
| 400 | `invalid_request` |
| 404 | `not_found` |
| 413 | `file_too_large` |
| 429 | `rate_limited` |
| 504 | `timeout` |
| 500 | `internal_error` |

## How a question is answered

1. **Retrieve:** BM25 top 20 and vector top 20 (bge-small with its query prefix) run in parallel, then Reciprocal Rank Fusion keeps 20 unique chunks.
2. **Rerank:** `BAAI/bge-reranker-base` rescores those 20 chunks and keeps the top 5.
3. **Abstain check:** if the best rerank score is below `ABSTAIN_THRESHOLD`, the system answers "not found" without calling the LLM.
4. **Generate:** the versioned prompt in [prompts/answer_v1.txt](prompts/answer_v1.txt) lists the chunks as `[1]…[5]` and requires a citation on every sentence, or `NOT_FOUND`.
5. **Verify citations:** answers with an uncited sentence, or a citation outside 1–5, are regenerated once with the violations listed. If the retry also fails, the system abstains.
6. **Respond:** the answer, citations (doc, page, snippet), token usage and cost, and stage latencies. Each request is logged to the `traces` table.

## Evaluation

```bash
python -m eval.build_golden   # rebuild eval/golden.jsonl after corpus or chunking changes
python -m eval.ablation       # retrieval ablation, written to eval/ablation.md
```

Current retrieval ablation on the 40 answerable golden questions:

| Configuration | Recall@5 | MRR@10 |
| --- | --- | --- |
| BM25 only | 1.000 | 0.975 |
| Vector only | 0.988 | 0.948 |
| Hybrid (RRF) | 1.000 | 1.000 |
| Hybrid + rerank | 1.000 | 0.988 |

The test corpus is small (41 chunks), so retrieval scores are close to the ceiling.

## Development

```bash
ruff check . && ruff format --check .
pytest --cov=askdocs
```
