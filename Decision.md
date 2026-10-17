# Architecture Decisions

## Context

Ask My Docs answers questions about one document collection, cites every claim, and abstains when the documents don't cover the question. It is two pipelines over one chunk store: offline ingestion builds a BM25 index and a vector index, and the online query pipeline fuses, reranks, generates and verifies citations.

These records replace the earlier Weaviate-based prototype decisions.

## Architecture Decision Records (ADRs)

| ADR ID | Area | Decision | Rationale | Alternative considered |
|--------|------|----------|-----------|------------------------|
| ADR 1 | Vector database | Qdrant (Docker) | Payload filters (e.g. `doc_id`), simple local run, and an in-memory mode that keeps tests and CI dependency-free. | Weaviate (prototype), Chroma |
| ADR 2 | Keyword index | `rank_bm25` in-process, rebuilt from SQLite | Zero extra infrastructure for v1; the chunk table is the source of truth, so rebuilding is cheap. | OpenSearch (later, for scale) |
| ADR 3 | Metadata store | SQLite via SQLAlchemy | Documents, chunks, traces and feedback in one file; moving to Postgres is a URL change. | Postgres from day one |
| ADR 4 | Embeddings | `BAAI/bge-small-en-v1.5`, local | Strong quality per cost and no API dependency; BGE query instruction prefix on queries only. | Hosted embedding API |
| ADR 5 | Chunking | Structure-aware: split by heading, then 512 tokens with 64-token overlap, never mid-sentence | Chunks stay inside one section, so citations map to a meaningful page and section. | Fixed 1,000-character windows |
| ADR 6 | Fusion | Reciprocal Rank Fusion, score = Σ 1 / (60 + rank) | No score calibration needed between BM25 and cosine scores. | Weighted score sum |
| ADR 7 | Reranker | `BAAI/bge-reranker-base` cross-encoder, 20 in → 5 out | Large precision gain on the top results while keeping CPU latency within budget. | 50 candidates (slower, small gain) |
| ADR 8 | Citation enforcement | Post-generation validator plus one retry, then abstain | Every sentence must cite a chunk in range; prompts alone are not reliable enough. | Trust the prompt only |
| ADR 9 | Abstention | Abstain when the best rerank score is below a threshold tuned on the eval set | Cheap and predictable; stops unsupported answers before calling the LLM. | LLM self-assessment only |
| ADR 10 | LLM | Claude (`claude-opus-5-5`) through the Anthropic SDK, behind a provider interface that also supports Ollama | Swappable backend; hosted for quality, local for offline demos. | Single hard-wired provider |
| ADR 11 | API | FastAPI + Uvicorn at `/api/v1`, SSE streaming | Async, typed, auto-generated OpenAPI docs. | Flask |
| ADR 12 | Frontend | React + TypeScript (Vite), Tailwind, TanStack Query | Streams answers with clickable citations; deploys as static files behind Nginx. | Server-rendered templates |
| ADR 13 | Evaluation | pytest + Ragas (faithfulness, correctness) plus custom retrieval, citation and abstention metrics | Runs in CI as a gate; thresholds live in `eval/thresholds.yaml`. | DeepEval |
| ADR 14 | Tracing | OpenTelemetry spans exported over OTLP to Arize Phoenix or Langfuse | One instrumentation, either backend; traces also stored locally with feedback. | Vendor-specific SDK |
