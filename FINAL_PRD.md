# Ask My Docs — Project 1 Build Pack

Oct 18, 2026 · @Mohan Sharma

Everything needed to build Project 1: a production RAG system with hybrid retrieval, cross-encoder reranking, enforced citations and a CI-gated evaluation pipeline.

## 1. Product Requirements (PRD)

**Problem.** People waste time searching long internal documents, and generic chatbots answer confidently without sources. Ask My Docs answers questions about one document collection, cites every claim, and says "not found" when the documents don't cover it.

**Target users.** Employees or customers who need fast, trustworthy answers from a fixed corpus — e.g. HR policies, product manuals, API docs, contracts. Pick one domain for v1 and collect 50–500 real documents.

### Scope

| In scope (v1) | Out of scope (v1) |
| --- | --- |
| PDF, Markdown, HTML, TXT ingestion | Scanned images / OCR-heavy docs |
| Single-turn Q&A with citations | Multi-turn memory, agents, tool use |
| Hybrid search + rerank | Multi-tenant permissions per document |
| Eval suite gated in CI | Fine-tuned models (that is Project 4) |
| Simple web UI + REST API | Mobile app |

### Functional requirements

1. **FR-1 Ingest** — upload or point to a folder; parse, chunk and index documents with source, page and section metadata.
2. **FR-2 Re-index** — re-ingesting a changed file replaces its old chunks (keyed by content hash).
3. **FR-3 Ask** — accept a natural-language question and return an answer in under the latency budget.
4. **FR-4 Cite** — every factual sentence ends with one or more `[n]` citations linking to the source chunk, file and page.
5. **FR-5 Abstain** — when retrieval confidence is low, reply that the answer is not in the documents.
6. **FR-6 Show sources** — UI shows the cited passages beside the answer.
7. **FR-7 Feedback** — users can mark an answer helpful or not; feedback is stored with the trace.

### Non-functional requirements

| Requirement | Target |
| --- | --- |
| End-to-end latency p95 | ≤ 4 s (≤ 1.5 s to first token when streaming) |
| Faithfulness (eval set) | ≥ 0.85 |
| Retrieval Recall@5 | ≥ 0.85 |
| Citation precision | ≥ 0.90 |
| Correct abstention on unanswerable questions | ≥ 0.80 |
| Cost per query | Logged; target set after first baseline |
| Reproducibility | One-command local run via Docker Compose |

### Success metrics

- All eval thresholds above pass in CI on the main branch.
- Ablation shows hybrid + rerank beats vector-only on Recall@5 and faithfulness.
- A reviewer can clone the repo and get a working demo in under 10 minutes.

## 2. Technical Design

The system is two pipelines over one chunk store: an offline ingestion pipeline that builds a BM25 index and a vector index, and an online query pipeline that fuses, reranks, generates and verifies citations.

### Chosen stack (v1)

| Layer | Choice | Why |
| --- | --- | --- |
| Language | Python 3.11+ | Ecosystem for every component |
| API | FastAPI + Uvicorn | Async, typed, streaming support |
| Parsing | PyMuPDF (PDF), BeautifulSoup (HTML), markdown-it | Keeps page/section metadata |
| Vector DB | Qdrant (Docker) | Payload filters, easy local run |
| Keyword index | rank\_bm25 (v1) → OpenSearch later | Zero infra to start |
| Metadata store | SQLite (v1) / Postgres | Chunks, documents, feedback |
| Embeddings | BAAI/bge-small-en-v1.5 (local) or a hosted embedding API | Strong quality per cost |
| Reranker | BAAI/bge-reranker-base cross-encoder | Large precision gain on top-k |
| LLM | Hosted API model, or local model via Ollama | Swappable behind one interface |
| UI | React + TypeScript (Vite) | Streams answers, clickable citations, deployable as static files |
| Eval | pytest + Ragas (or DeepEval) | Runs in CI |
| Tracing | Langfuse or Arize Phoenix | Feeds Project 3 |

### Data model

| Table | Key fields |
| --- | --- |
| documents | doc\_id, file\_name, source\_uri, content\_hash, title, ingested\_at |
| chunks | chunk\_id, doc\_id, text, page, section\_path, token\_count, position |
| feedback | query\_id, question, answer, cited\_chunk\_ids, rating, created\_at |

The vector point id equals `chunk_id`; its payload holds `doc_id`, `page` and `section_path` so citations can be rendered without a second lookup.

### Ingestion design

1. Detect file type and extract text per page, keeping heading hierarchy.
2. Normalize whitespace, strip headers/footers repeated on every page.
3. Chunk by heading first, then split to 512 tokens with 64-token overlap; never split mid-sentence.
4. Prepend a short context header to each chunk (document title + section path) before embedding.
5. Compute `content_hash`; skip unchanged files, delete-then-insert changed ones.
6. Write chunks to SQLite, BM25 index and Qdrant in one job; log counts.

### Query design

1. **Query prep** — lowercase/normalize for BM25; embed with the query instruction prefix the embedding model expects.
2. **Hybrid retrieval** — BM25 top 20 and vector top 20, in parallel.
3. **Fusion** — Reciprocal Rank Fusion, score = Σ 1 / (60 + rank); keep top 20 unique chunks.
4. **Rerank** — cross-encoder scores (question, chunk) pairs; keep top 5.
5. **Abstain check** — if the best rerank score is below a tuned threshold, return the not-found response.
6. **Generate** — prompt with numbered chunks `[1]…[5]`, instructions to cite each sentence and to say "not found" if unsupported; temperature 0–0.2.
7. **Verify citations** — parse `[n]` markers; drop answers with uncited sentences or citations outside 1–5, then regenerate once or abstain.
8. **Respond** — answer, citations (doc, page, snippet), latency and token usage; log a trace.

### Key design decisions

| Decision | Choice | Alternative considered |
| --- | --- | --- |
| Fusion method | RRF (no score calibration needed) | Weighted score sum |
| Rerank depth | 20 in → 5 out | 50 in (slower, small gain) |
| Citation enforcement | Post-generation validator + one retry | Trust the prompt only |
| Chunking | Structure-aware, 512 tokens | Fixed 1,000-char windows |

### Frontend design (React)

A React + TypeScript single-page app built with Vite talks to the FastAPI backend over REST and streams answers via server-sent events.

| Concern | Choice |
| --- | --- |
| Build tool | Vite |
| Styling | Tailwind CSS (optionally shadcn/ui components) |
| Server state | TanStack Query for documents, ingest jobs, feedback |
| Streaming | `fetch` + ReadableStream on `/api/v1/ask/stream` (SSE) |
| Markdown rendering | react-markdown, with `[n]` turned into citation buttons |
| Testing | Vitest + React Testing Library; Playwright for one end-to-end flow |

**Components**

1. `AskBox` — question input, submit, stop-generation button.
2. `AnswerView` — renders tokens as they stream; each `[n]` is a clickable chip.
3. `CitationPanel` — side panel showing file name, page and the highlighted snippet for the selected citation.
4. `Feedback` — helpful / not helpful buttons posting to `/api/v1/feedback`.
5. `UploadPanel` — drag-and-drop files to `/api/v1/ingest`, polls job status, lists indexed documents.
6. `NotFoundState` — clear message when the system abstains.

**Integration notes**

- Enable CORS in FastAPI for `http://localhost:5173` during development.
- API base URL comes from `VITE_API_URL` in `frontend/.env`.
- In Docker Compose, add a `frontend` service (Nginx serving `npm run build` output) beside `api` and `qdrant`.

## 3. Architecture

&#91;embedded content: Ask My Docs architecture · ingestion and query pipelines\]

Ingestion writes each chunk to both indexes (and to SQLite for metadata); at query time both indexes are searched, fused, reranked, and only a confident, fully cited answer is returned.

## 4. API Specification

REST API served by FastAPI at `/api/v1`, JSON in and out; OpenAPI docs auto-generated at `/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /api/v1/ingest | Upload files or a folder path to index |
| GET | /api/v1/ingest/{job\_id} | Ingestion job status and counts |
| POST | /api/v1/ask | Ask a question, get a cited answer |
| POST | /api/v1/ask/stream | Same, streamed as server-sent events |
| GET | /api/v1/documents | List indexed documents |
| DELETE | /api/v1/documents/{doc\_id} | Remove a document and its chunks |
| POST | /api/v1/feedback | Rate an answer |
| GET | /api/v1/health | Liveness and dependency checks |

### POST /api/v1/ask

Request:

```json
{
  "question": "How many days of parental leave do employees get?",
  "top_k": 5,
  "filters": {"doc_ids": ["hr-handbook-2026"]}
}
```

Response (200):

```json
{
  "query_id": "q_01HZX...",
  "answer": "Employees get 26 weeks of paid parental leave [1], which can be split into two blocks [2].",
  "abstained": false,
  "citations": [
    {"n": 1, "chunk_id": "c_812", "doc_id": "hr-handbook-2026", "file_name": "HR_Handbook.pdf", "page": 14, "snippet": "..."},
    {"n": 2, "chunk_id": "c_815", "doc_id": "hr-handbook-2026", "file_name": "HR_Handbook.pdf", "page": 15, "snippet": "..."}
  ],
  "usage": {"input_tokens": 2140, "output_tokens": 64, "cost_usd": 0.0021},
  "latency_ms": {"retrieve": 85, "rerank": 210, "generate": 1320, "total": 1650}
}
```

The numbers above are placeholder sample values for illustration.

### Errors

| Status | Code | When |
| --- | --- | --- |
| 400 | invalid\_request | Empty question or bad filters |
| 404 | not\_found | Unknown doc\_id or job\_id |
| 413 | file\_too\_large | Upload above the size limit |
| 429 | rate\_limited | Upstream LLM rate limit |
| 504 | timeout | A pipeline stage exceeded its timeout |
| 500 | internal\_error | Anything else (trace id returned) |

## 5. Evaluation Plan

No change merges unless the golden-set eval passes every threshold; the eval runs in under 10 minutes on each pull request.

### Golden set

- 100–200 questions written from the real corpus (start with 50, grow over time).
- Mix: \~60% single-fact, \~20% multi-chunk (answer spans 2+ sections), \~20% unanswerable.
- Each item stores the expected answer and the chunk ids that support it.
- Stored as `eval/golden.jsonl`, versioned in git; never used for prompt tuning by hand-picking.

```json
{"id": "g_042", "question": "What is the notice period for resignation?", "expected_answer": "30 days for all full-time staff.", "supporting_chunk_ids": ["c_233"], "answerable": true, "tags": ["single-fact", "hr"]}
```

### Metrics and thresholds

| Stage | Metric | Threshold to pass |
| --- | --- | --- |
| Retrieval | Recall@5 (supporting chunk in top 5 after rerank) | ≥ 0.85 |
| Retrieval | MRR@10 | ≥ 0.70 |
| Generation | Faithfulness (claims supported by cited chunks, LLM-judged) | ≥ 0.85 |
| Generation | Answer correctness vs expected answer | ≥ 0.75 |
| Citations | Citation precision (cited chunk actually supports sentence) | ≥ 0.90 |
| Abstention | Correct "not found" on unanswerable items | ≥ 0.80 |
| Abstention | False abstention on answerable items | ≤ 0.10 |
| Performance | p95 latency on eval run | ≤ 4 s |

Thresholds are starting points; set final values from the first baseline run and only ratchet them up.

### Ablation runs (report in README)

1. BM25 only
2. Vector only
3. Hybrid (RRF)
4. Hybrid + cross-encoder rerank
5. Hybrid + rerank + citation validator

### CI gate

1. GitHub Actions workflow `eval.yml` triggers on pull requests touching `src/`, `prompts/` or `eval/`.
2. Spin up Qdrant as a service container; ingest the fixed test corpus in `eval/corpus/`.
3. Run `pytest eval/` which computes all metrics and writes `eval/report.json`.
4. Compare against thresholds in `eval/thresholds.yaml`; fail the job on any breach.
5. Post the metrics table as a PR comment and upload the report as an artifact.
6. Store API keys as repository secrets; cache model downloads to keep runs fast.

## 6. Repo Structure & Setup

One repository, one `docker compose up` to run the API, UI and Qdrant locally.

### Folder layout

```text
ask-my-docs/
├── src/askdocs/
│   ├── ingest/        # parsers.py, chunker.py, indexer.py
│   ├── retrieve/      # bm25.py, vector.py, fusion.py
│   ├── rerank/        # cross_encoder.py
│   ├── generate/      # prompt.py, llm.py, citations.py
│   ├── api/           # main.py, routes.py, schemas.py
│   ├── store/         # db.py, models.py
│   └── config.py
├── frontend/          # React + TypeScript (Vite)
│   ├── src/components/  # AskBox, AnswerView, CitationPanel, Feedback, UploadPanel
│   ├── src/api/         # client.ts: fetch + SSE streaming
│   ├── src/App.tsx
│   ├── package.json
│   └── vite.config.ts
├── prompts/           # answer_v1.txt
├── eval/
│   ├── corpus/        # fixed test documents
│   ├── golden.jsonl
│   ├── thresholds.yaml
│   └── test_eval.py
├── tests/             # unit tests per module
├── data/              # local uploads (git-ignored)
├── .github/workflows/ # ci.yml, eval.yml
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
└── README.md
```

### Prerequisites

- Python 3.11+, Node.js 20+ with npm, Docker Desktop, Git
- 8 GB RAM minimum (16 GB if running embeddings, reranker and a local LLM together)
- An LLM API key, or Ollama installed for a local model

### Setup steps

1. `git clone` the repo and `cd ask-my-docs`
2. `python -m venv .venv` and activate it
3. `pip install -e ".[dev]"`
4. `cp .env.example .env` and fill in keys
5. `docker compose up -d qdrant`
6. `python -m askdocs.ingest --path data/docs`
7. `uvicorn askdocs.api.main:app --reload`
8. `cd frontend && npm install && npm run dev (opens http://localhost:5173)`
9. `pytest tests/` then `pytest eval/` to confirm the baseline

### Configuration (.env)

| Variable | Example | Purpose |
| --- | --- | --- |
| LLM\_PROVIDER | openai / anthropic / ollama | Which LLM backend |
| LLM\_MODEL | model name | Generation model |
| LLM\_API\_KEY | (secret) | Provider key |
| EMBED\_MODEL | BAAI/bge-small-en-v1.5 | Embedding model |
| RERANK\_MODEL | BAAI/bge-reranker-base | Cross-encoder |
| QDRANT\_URL | http://localhost:6333 | Vector DB |
| CHUNK\_SIZE / CHUNK\_OVERLAP | 512 / 64 | Chunking (tokens) |
| RETRIEVE\_K / RERANK\_K | 20 / 5 | Retrieval depth |
| ABSTAIN\_THRESHOLD | tuned on eval set | Not-found cutoff |
| TRACING\_ENABLED | true | Send traces to Langfuse/Phoenix |

## 7. Build Plan

Three weeks part-time (\~10 hrs/week), five phases; each phase ends with something runnable.

### Phase 0 — Setup (days 1–2)

- [ ] Choose the domain and collect 50–500 documents
- [ ] Create repo skeleton, `pyproject.toml`, `.env.example`, Docker Compose with Qdrant
- [ ] Add `ci.yml` with lint (ruff) and unit tests

### Phase 1 — Ingestion (days 3–5)

- [ ] Parsers for PDF, Markdown, HTML, TXT with page/section metadata
- [ ] Structure-aware chunker with overlap and unit tests
- [ ] SQLite schema for documents and chunks; content-hash re-indexing
- [ ] BM25 index build and Qdrant upsert
- [ ] Milestone: `python -m askdocs.ingest` indexes the full corpus

### Phase 2 — Retrieval & rerank (days 6–9)

- [ ] BM25 and vector search functions
- [ ] RRF fusion
- [ ] Cross-encoder rerank
- [ ] Write the first 50 golden questions with supporting chunk ids
- [ ] Milestone: Recall@5 measured for BM25, vector, hybrid, hybrid + rerank

### Phase 3 — Generation & citations (days 10–13)

- [ ] Prompt template with numbered chunks and citation rules
- [ ] LLM client interface (hosted + Ollama)
- [ ] Citation validator + one retry, abstention threshold
- [ ] `/ask` and `/ask/stream` endpoints
- [ ] Milestone: cited answers returned through the API

### Phase 4 — Evaluation & CI gate (days 14–17)

- [ ] Faithfulness, correctness, citation precision, abstention metrics
- [ ] `thresholds.yaml` set from the baseline
- [ ] `eval.yml` GitHub Actions workflow with PR comment
- [ ] Milestone: a deliberately bad prompt change fails CI

### Phase 5 — UI, tracing & polish (days 18–21)

- [ ] React UI: ask box, streamed answer, clickable \[n\] citations, source panel, document upload
- [ ] Feedback endpoint and buttons
- [ ] Tracing to Langfuse/Phoenix (ready for Project 3)
- [ ] README: demo GIF, architecture diagram, ablation table, trade-offs
- [ ] Milestone: fresh clone to working demo in under 10 minutes

## 8. Risks, Open Questions & Definition of Done

### Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Poor PDF parsing (tables, columns) | Wrong chunks, low recall | Test parsers on 10 hard docs first; try Docling for complex layouts |
| Golden set too small or biased | Misleading metrics | Write questions before tuning; include unanswerable and multi-chunk items |
| LLM-as-judge noise | Flaky CI | Fix judge model + temperature 0; average over the set; small tolerance margin |
| Reranker latency on CPU | p95 above budget | Rerank 20 not 50; use a small reranker or GPU; cache embeddings |
| API cost during CI | Unexpected bills | Small fixed eval corpus; run full eval only on PRs to main |
| Over-abstention | Unhelpful answers | Tune threshold on eval set; track false-abstention rate |

### Open questions

- Which domain and document set will v1 use?
- Hosted LLM or fully local via Ollama for the demo?
- Is a public demo deployment needed (e.g. Hugging Face Spaces, Render), or local only?

### Definition of Done

- [ ] All functional requirements FR-1 to FR-7 work end to end
- [ ] Every eval threshold passes on main in CI
- [ ] Ablation table published in the README
- [ ] A failing PR demonstrates the CI gate blocks regressions
- [ ] Unit test coverage ≥ 70% on `src/`
- [ ] README with demo, architecture, setup, results and trade-offs
- [ ] Traces visible in the tracing tool for every request
