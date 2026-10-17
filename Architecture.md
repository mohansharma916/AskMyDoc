# System Architecture

## 1. System Overview

Ask My Docs is two pipelines over one chunk store:

- **Ingestion (offline):** parses documents, chunks them by structure, and writes every chunk to SQLite (metadata), Qdrant (vectors) and a BM25 keyword index.
- **Query (online):** searches both indexes, fuses the results, reranks them, generates an answer from numbered chunks, and verifies the citations before returning. If retrieval confidence is low or the citations don't check out, it returns a "not found" answer instead.

A React frontend talks to a FastAPI backend over REST and streams answers over server-sent events.

## 2. Component Architecture

### 2.1 Ingestion (`src/askdocs/ingest/`)

- **Parsers:** PyMuPDF (PDF), BeautifulSoup (HTML) and markdown-it (Markdown) parse each file; plain text splits on blank lines. Each block records its page and heading path. PDF headings are detected by font size, and headers or footers repeated on most pages are removed.
- **Chunker:** splits by section first, then packs whole sentences up to 512 tokens with 64 tokens of overlap.
- **Indexer:** computes a `content_hash` per file and skips unchanged files. Changed files are deleted and re-inserted. Before embedding, each chunk gets a short header with the document title and section path.
- **CLI:** `python -m askdocs.ingest --path <file-or-folder>`

### 2.2 Retrieval and rerank (`src/askdocs/retrieve/`, `src/askdocs/rerank/`)

- **BM25:** `rank_bm25`, rebuilt from the chunk table whenever it changes.
- **Vector search:** Qdrant with cosine similarity. Each point id is its `chunk_id`, and the payload holds `doc_id`, `page`, `section_path` and the text.
- **Fusion:** Reciprocal Rank Fusion of the top 20 from each index, keeping the top 20 unique chunks.
- **Rerank:** the `BAAI/bge-reranker-base` cross-encoder scores the 20 candidates and keeps the top 5.

### 2.3 Generation (`src/askdocs/generate/`)

- **Prompt:** numbered chunks `[1]…[5]` with rules to cite every sentence and to say "not found" when the chunks don't support an answer.
- **LLM interface:** Claude through the Anthropic SDK, or a local model via Ollama.
- **Citation validator:** parses the `[n]` markers and rejects answers with uncited sentences or with citations outside 1–5. It then regenerates once, or abstains.

### 2.4 API (`src/askdocs/api/`)

FastAPI at `/api/v1`: `ingest` (background jobs), `ask`, `ask/stream` (SSE), `documents`, `feedback` and `health`. OpenAPI docs are served at `/docs`. Errors share one JSON shape with a trace id.

### 2.5 Frontend (`frontend/`)

React + TypeScript (Vite, Tailwind, TanStack Query) with these components:

- **AskBox:** question input, with a stop-generation button.
- **AnswerView:** renders streamed tokens; each `[n]` is a clickable chip.
- **CitationPanel:** shows the file, page and section of a cited source, highlighting the words it shares with the citing sentence.
- **Feedback:** helpful / not helpful buttons.
- **UploadPanel:** drag-and-drop ingest with job polling.
- **NotFoundState:** shown when the system abstains.

In Docker, Nginx serves the build and proxies `/api`, with buffering off for server-sent events.

### 2.6 Tracing (`src/askdocs/tracing.py`)

Each request produces an OpenTelemetry trace: an `ask` root span with `retrieve`, `rerank` and one `generate` span per attempt. Traces are exported over OTLP/HTTP to Arize Phoenix or Langfuse. The trace id is returned to the client and stored on the `traces` row next to any feedback.

### 2.7 Store (`src/askdocs/store/`)

| Table | Key fields |
|-------|------------|
| documents | doc_id, file_name, source_uri, content_hash, title, ingested_at |
| chunks | chunk_id, doc_id, text, page, section_path, token_count, position |
| traces | query_id, question, answer, abstained, citations, context_chunk_ids, usage, latency_ms, prompt_version, otel_trace_id |
| feedback | query_id, question, answer, cited_chunk_ids, rating, comment, created_at |

## 3. Data Flow

### 3.1 Ingestion

```text
Files ──> Parser (page + section) ──> Chunker (512 tok / 64 overlap) ──> content_hash check
      ──> SQLite (documents, chunks) + Qdrant (vectors) + BM25 index
```

### 3.2 Query

```text
Question ──> BM25 top 20 ─┐
         └─> Vector top 20 ┴─> RRF top 20 ──> Cross-encoder top 5 ──> Abstain check
         ──> LLM with numbered chunks ──> Citation validator (retry once) ──> Answer + citations + trace
```

### 3.3 Evaluation (CI gate)

```text
eval/corpus ──> ingest ──> eval/golden.jsonl questions ──> query pipeline
            ──> Recall@5, MRR@10, faithfulness, correctness, citation precision, abstention, p95 latency
            ──> eval/thresholds.yaml ──> pass / fail + PR comment
```

### 3.4 Deployment

```text
docker compose up ──> qdrant (6333) + api (FastAPI, 8000) + frontend (Nginx, 8080) [+ phoenix (6006) with --profile tracing]
```
