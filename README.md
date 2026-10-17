# Ask My Docs

Ask My Docs answers questions about one document collection. Every sentence of an answer is cited, and the system says "not found" when the documents don't cover the question.

It is a production-style RAG system with:

- hybrid retrieval: BM25 and vector search, fused with Reciprocal Rank Fusion (RRF)
- cross-encoder reranking
- citation validation, with one retry before abstaining
- a golden-set evaluation that gates pull requests in CI

- **Design:** [Architecture.md](Architecture.md)
- **Decision records:** [Decision.md](Decision.md)

## Quick start (Docker)

Prerequisites: Docker and an Anthropic API key.

```bash
cp .env.example .env               # set LLM_API_KEY
docker compose up -d --build       # Qdrant, API and web UI
docker compose exec api python -m askdocs.ingest --path eval/corpus
```

- **Web UI:** http://localhost:8080
- **API docs:** http://localhost:8000/docs

If a port is taken, override it, for example `API_PORT=8001 UI_PORT=8081 docker compose up -d`. The first start downloads the embedding and reranker models (about 1.2 GB) into a Docker volume.

To add tracing, run `docker compose --profile tracing up -d` and set `TRACING_ENABLED=true`. Traces then appear in Arize Phoenix at http://localhost:6006.

## Local development

Prerequisites: Python 3.11+, Node.js 20+, Docker.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,eval]"
cp .env.example .env                              # set LLM_API_KEY
docker compose up -d qdrant
python -m askdocs.ingest --path eval/corpus
uvicorn askdocs.api.main:app --reload             # http://localhost:8000/docs

cd frontend && cp .env.example .env && npm install && npm run dev   # http://localhost:5173
```

To use a local model instead of Claude, set `LLM_PROVIDER=ollama` and `LLM_MODEL=<a model you've pulled>`.

## How a question is answered

```text
question ──> BM25 top 20 ─┐
         └─> vector top 20 ┴─> RRF top 20 ──> cross-encoder top 5 ──> abstain check
         ──> Claude with numbered chunks [1]…[5] ──> citation validator (retry once) ──> answer + citations
```

1. **Retrieve:** BM25 (`rank_bm25`) and Qdrant vector search (`bge-small-en-v1.5`, with its query prefix) run in parallel. RRF fuses the results (score = Σ 1/(60 + rank)) and keeps 20 unique chunks.
2. **Rerank:** `BAAI/bge-reranker-base` scores each (question, chunk) pair and keeps the top 5.
3. **Abstain check:** if the best rerank score is below `ABSTAIN_THRESHOLD`, the answer is "not found" and the LLM is never called.
4. **Generate:** the versioned prompt [prompts/answer_v1.txt](prompts/answer_v1.txt) requires a citation on every sentence, or `NOT_FOUND`.
5. **Verify citations:** an answer with an uncited sentence, or a citation outside 1–5, is regenerated once with the violations listed. If the retry also fails, the system abstains.
6. **Respond:** the answer comes back with citations (file, page, section, snippet), token usage and cost, and per-stage latency. Each request is stored in the `traces` table, and as an OpenTelemetry trace when tracing is on.

Ingestion parses PDF (PyMuPDF), HTML (BeautifulSoup), Markdown (markdown-it) and TXT files, keeping each block's page and heading path. PDFs also have their running headers and footers removed. Chunking splits by section first, then into 512-token chunks with 64 tokens of overlap, never mid-sentence. Before embedding, each chunk gets its document title and section path prepended. Re-ingesting a file is keyed by its content hash: unchanged files are skipped, and changed files are deleted and re-inserted.

## API

All endpoints are under `/api/v1`. The OpenAPI docs are at `/docs`.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/ingest` | Upload `files`, or give a `path` under `INGEST_ROOT`; returns a background job |
| GET | `/ingest/{job_id}` | Job status and per-file counts |
| POST | `/ask` | Cited answer, with usage, latency and trace id |
| POST | `/ask/stream` | The same answer as server-sent events: `meta`, `token`, `retry`, `done` or `error` |
| GET | `/documents` | Indexed documents |
| DELETE | `/documents/{doc_id}` | Remove a document and its chunks |
| POST | `/feedback` | Rate an answer `helpful` or `not_helpful`; stored with its trace |
| GET | `/health` | Database, Qdrant and LLM configuration checks |

Errors share one shape, `{"error": {"code", "message", "trace_id"}}`:

| Status | Code | When |
|--------|------|------|
| 400 | `invalid_request` | Empty question or bad filters |
| 404 | `not_found` | Unknown `doc_id` or `job_id` |
| 413 | `file_too_large` | Upload above the size limit |
| 429 | `rate_limited` | Upstream LLM rate limit |
| 504 | `timeout` | A pipeline stage exceeded its timeout |
| 500 | `internal_error` | Anything else (trace id returned) |

## Evaluation

The fixed test corpus in `eval/corpus/` holds five fictional HR policies, one per supported format. The golden set has 50 questions: 30 single-fact, 10 multi-chunk and 10 unanswerable. Each question is written in [eval/golden_source.yaml](eval/golden_source.yaml) with exact evidence quotes, and `python -m eval.build_golden` maps those quotes to supporting chunk ids in `eval/golden.jsonl`. A unit test fails if the golden file drifts from the corpus or the chunking settings.

```bash
pytest eval/                      # full gate: needs LLM_API_KEY; writes eval/report.json and report.md
python -m eval.ablation           # retrieval ablation (no LLM calls); add --generation for answer metrics
python -m eval.tune_threshold     # pick ABSTAIN_THRESHOLD from the golden set
```

| Metric | Threshold ([eval/thresholds.yaml](eval/thresholds.yaml)) |
|--------|------|
| Recall@5 (supporting chunk in top 5 after rerank) | ≥ 0.85 |
| MRR@10 | ≥ 0.70 |
| Faithfulness (Ragas, Claude as judge) | ≥ 0.85 |
| Answer correctness (Ragas factual correctness) | ≥ 0.75 |
| Citation precision (Claude judges each sentence and cited excerpt pair) | ≥ 0.90 |
| Correct abstention on unanswerable questions | ≥ 0.80 |
| False abstention on answerable questions | ≤ 0.10 |
| p95 latency | ≤ 4000 ms |

### Ablation (retrieval)

| Configuration | Recall@5 | MRR@10 |
| --- | --- | --- |
| BM25 only | 1.000 | 0.975 |
| Vector only | 0.988 | 0.948 |
| Hybrid (RRF) | 1.000 | 1.000 |
| Hybrid + rerank | 1.000 | 0.988 |
| Hybrid + rerank + citation validator | 1.000 | 0.988 |

These figures come from 40 answerable golden questions. The corpus has only 41 chunks, so retrieval sits near the ceiling. Hybrid retrieval beats vector-only on both metrics; the cross-encoder slightly reorders already-correct results.

The generation columns (faithfulness, citation precision and correctness per configuration) come from `python -m eval.ablation --generation`, which needs an API key.

The abstention threshold is tuned with `eval.tune_threshold`. At 0.03, 9 of the 10 unanswerable questions are stopped before the LLM is called, with no false abstentions. The model's own `NOT_FOUND` reply handles the remaining one.

### CI gate

- **`ci.yml`:** on every push to main and every pull request, it runs ruff, the unit tests (with a 70% coverage floor), and the frontend typecheck, tests, build and Playwright flow.
- **`eval.yml`:** on pull requests to main that touch `src/`, `prompts/` or `eval/`, it:
  - starts Qdrant as a service and ingests `eval/corpus`
  - runs `pytest eval/` against the thresholds
  - posts the metrics table as a PR comment and uploads `report.json`

The gate fails, rather than skipping, if the `ANTHROPIC_API_KEY` repository secret is missing. Set the `JUDGE_MODEL` repository variable to use a cheaper judge model.

## Configuration

Every setting has a default in [src/askdocs/config.py](src/askdocs/config.py) and can be overridden in `.env`; see [.env.example](.env.example) for the full list. The main settings:

| Variable | Default | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_API_KEY` | `anthropic` / `claude-opus-5-5` / – | Generation backend (`anthropic` or `ollama`) |
| `LLM_EFFORT` | `low` | Claude effort level, kept low for the latency budget |
| `EMBED_MODEL` / `RERANK_MODEL` | `BAAI/bge-small-en-v1.5` / `BAAI/bge-reranker-base` | Local models |
| `QDRANT_URL` | `http://localhost:6333` | Vector DB (`:memory:` or a local path also work) |
| `DATABASE_URL` | `sqlite:///data/askdocs.db` | Documents, chunks, traces, feedback |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | 512 / 64 | Chunking, in tokens |
| `RETRIEVE_K` / `RERANK_K` | 20 / 5 | Retrieval depth |
| `ABSTAIN_THRESHOLD` | 0.03 | Minimum best rerank score |
| `TRACING_ENABLED` / `OTEL_ENDPOINT` | `false` / Phoenix | OpenTelemetry export (Langfuse also works through `OTEL_EXPORTER_OTLP_HEADERS`) |

## Project layout

```text
src/askdocs/
  ingest/      parsers.py, pdf.py, chunker.py, indexer.py, __main__.py (CLI)
  retrieve/    bm25.py, vector.py, embeddings.py, fusion.py, hybrid.py
  rerank/      cross_encoder.py
  generate/    prompt.py, llm.py, citations.py
  api/         main.py, routes.py, schemas.py, errors.py, jobs.py
  store/       db.py, models.py
  pipeline.py  services.py  tracing.py  config.py
frontend/      React + TypeScript: AskBox, AnswerView, CitationPanel, Feedback, UploadPanel, NotFoundState
prompts/       answer_v1.txt
eval/          corpus/, golden_source.yaml, golden.jsonl, thresholds.yaml, test_eval.py, ablation.py
tests/         unit tests (models are faked; no downloads or API calls)
```

## Trade-offs and limitations

- **Latency:** reranking 20 chunks with `bge-reranker-base` dominates retrieval time. Models are loaded at startup, so the first request doesn't pay the multi-second load. Warm rerank times measured on one Apple Silicon Mac:

  | Where it runs | Rerank time |
  |---------------|-------------|
  | Native, MPS GPU | ~1.1 s |
  | Native, CPU only | 1.8 s |
  | Docker (Linux CPU build of PyTorch) | 7–8 s |

  The Docker figure exceeds the 4 s p95 budget. Either run the API natively, deploy on a GPU or a fast x86 server, or switch to `RERANK_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2` (0.7 s in Docker). A different reranker scores differently, so re-run `python -m eval.tune_threshold` after switching.
- **Sampling:** current Claude models reject sampling parameters, so the "temperature 0–0.2" guidance can't be applied to generation or judging. Effort is fixed instead, and judge noise is averaged over the whole set. `LLM_TEMPERATURE` applies only to Ollama.
- **Eval cost:** each `pytest eval/` run makes a few hundred Claude calls for answers, the citation judge and Ragas. Use `JUDGE_MODEL` to lower the cost.
- **Small corpus:** the golden set is small and lexically close to its corpus, so the ablation barely separates the configurations. Add paraphrased and harder questions as the corpus grows.
- **Migrations:** schema changes are additive only; nullable columns are added automatically on startup. Anything else needs a real migration tool such as Alembic.
- **Out of scope for v1:** OCR, multi-turn chat, and per-document permissions.

## Development

```bash
ruff check . && ruff format --check .
pytest --cov=askdocs                  # unit tests
cd frontend && npm run typecheck && npm test && npm run e2e
```
