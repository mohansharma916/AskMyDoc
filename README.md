# Multi-Phase RAG Demonstrator

An "ask my doc" app that runs the same question through three RAG maturity levels, built from [PRD.md](PRD.md), [Decision.md](Decision.md) and [Architecture.md](Architecture.md).

| Phase | Pipeline |
|-------|----------|
| 1 · Fundamentals | Weaviate vector search → top K chunks → base prompt → Claude → cited answer |
| 2 · Production Quality | Weaviate hybrid search (BM25 + vector) → cross-encoder re-ranker → citation guardrail → versioned prompt → Claude → cited answer, or a refusal when the documents don't support one |
| 3 · Shippable System | Golden dataset → Ragas (faithfulness, answer relevancy, context recall) → CI-style pass/fail build against thresholds; live queries also get a per-answer faithfulness score |

## Stack

- **Frontend:** React + Vite (`frontend/`)
- **Backend:** FastAPI (`backend/app/`)
- **Routing:** a LangGraph `StateGraph` picks the path from `phase_target` ([graph.py](backend/app/graph.py))
- **Vector DB:** Weaviate, run with Docker. Embeddings are computed locally with sentence-transformers.
- **LLM:** Claude (`claude-opus-5-5`) through the official Anthropic SDK, with server-side refusal fallback enabled
- **Re-ranker:** Cohere `rerank-v3.5`. You can swap in a local cross-encoder with `RERANKER=local` (no API key needed).
- **Evaluation:** Ragas, with Claude as the judge model

## Quick start

Prerequisites: Docker, Python 3.10+, and Node 18+.

```bash
# 1. Vector database
docker compose up -d

# 2. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set ANTHROPIC_API_KEY (and COHERE_API_KEY, or RERANKER=local)
uvicorn app.main:app --port 8001 --reload

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8001`. To use a different backend address, set `BACKEND_URL`.

### Try it with the sample data

1. Upload `sample_data/northwind_handbook.md` from the sidebar.
2. In Phase 1 or 2, ask "How many PTO days do I get per year?"
3. In Phase 2, ask something the handbook doesn't cover, such as "What is the CEO's salary?". Phase 2 declines; Phase 1 answers anyway.
4. In Phase 3, upload `sample_data/golden_dataset.json` and click **Run evaluation**.

The sample golden set has 12 pairs, so the UI warns that it is below the recommended 50–200.

## API

| Endpoint | Description |
|----------|-------------|
| `POST /upload` | Multipart `files`: PDF, Markdown, or text. Chunks are 800 tokens with 100 tokens of overlap. Re-uploading a file replaces its chunks. |
| `GET /documents`, `DELETE /documents[/{source}]` | List or remove indexed documents. |
| `POST /query` | `{"question": "...", "phase_target": 1 \| 2 \| 3}`. Returns the answer, citations, the pipeline trace with timings, and the prompt version. |
| `GET /prompts` | The versioned prompts from [prompts.yaml](backend/prompts.yaml). |
| `GET/POST /golden` | View or upload the golden dataset. Accepts a JSON list or a CSV with `question` and `ground_truth` (or `answer`) columns. |
| `POST /evaluate` | `{"pipeline_phase": 1 \| 2, "limit": null}`. Starts a background Ragas run and returns a job. |
| `GET /evaluate/{id}`, `GET /evaluate/history` | Job progress and result; build history with thresholds. |

## CI usage

`scripts/run_eval.py` runs the same evaluation headlessly. It exits with code 1 when any quality gate fails, so it can be used as a CI step:

```bash
cd backend && python -m scripts.run_eval --phase 2
```

You set the thresholds in `.env` (`THRESHOLD_FAITHFULNESS`, `THRESHOLD_ANSWER_RELEVANCY`, `THRESHOLD_CONTEXT_RECALL`).

## Configuration notes

- **Prompt versions:** change a template in `prompts.yaml` and bump its `version`. The UI shows the version each answer used.
- **Guardrail threshold:** Phase 2 declines when no re-ranked chunk scores at least `RERANK_MIN_SCORE`, or when the Claude guardrail judges that the passages don't support an answer.
- **Embedding model:** the default `BAAI/bge-small-en-v1.5` reads at most 512 tokens per chunk, so the tail of an 800-token chunk isn't embedded. BM25 and the re-ranker still see the full text. For full-chunk embeddings, use a long-context model in `EMBEDDING_MODEL`. Changing the model means re-uploading your documents.
- **Data storage:** golden datasets and build history are stored in `backend/data/`.
