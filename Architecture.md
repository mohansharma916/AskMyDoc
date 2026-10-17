# System Architecture

## 1. System Overview

The application follows a decoupled client-server architecture. The React frontend handles user interactions and file uploads. The FastAPI backend orchestrates document ingestion and query routing through LangChain and LangGraph.

## 2. Component Architecture

### 2.1 Frontend (React)

- **Upload Manager:** Multipart form data submission for documents and golden datasets.
- **Phase Controller:** State manager that appends a `phase_target` metadata flag to the user's query payload.
- **Results Renderer:** Renders markdown answers, highlights exact source citations, and visualizes Ragas evaluation metrics.

### 2.2 Backend API (FastAPI)

| Endpoint | Description |
|----------|-------------|
| `/upload` | Handles incoming PDFs and markdown files. |
| `/query` | Accepts the user query and the `phase_target` (1, 2, or 3). |
| `/evaluate` | Triggers the Ragas offline evaluation script against the golden dataset. |

### 2.3 RAG Engine (LangChain / LangGraph)

- **Ingestion Pipeline:** Reads files → Text Splitter (500–800 tokens, 100 overlap) → Embedding Model → Weaviate.
- **Execution Router:**
  - **Path 1 (Phase 1):** Weaviate Vector Search → Top K Chunks → Base Prompt → LLM → Response.
  - **Path 2 (Phase 2):** Weaviate Hybrid Search (BM25 + Vector) → Cohere Cross-Encoder Re-ranker → Citation Guardrail Node → Versioned Prompt → LLM → Response.
  - **Path 3 (Phase 3):** Ragas Evaluation Pipeline → Compares LLM outputs against the 50–200 golden QA pairs → Returns Faithfulness Metrics.

## 3. Data Flow Diagram

### 3.1 Document Ingestion (Common)

```text
User ──> UI Upload ──> FastAPI (/upload) ──> LangChain Splitter ──> Embeddings ──> Weaviate Vector Store
```

### 3.2 Query Execution (Phase 1)

```text
User ──> Selects Phase 1 ──> FastAPI (/query) ──> Vector Search Only ──> LLM Generation ──> Cites Exact Source
```

### 3.3 Query Execution (Phase 2)

```text
User ──> Selects Phase 2 ──> FastAPI (/query) ──> Hybrid Search ──> Cohere Re-ranker ──> LLM Guardrail (Check Support) ──> LLM Generation ──> Cites Exact Source
```

### 3.4 System Evaluation (Phase 3)

```text
User ──> Uploads Golden Dataset ──> FastAPI (/evaluate) ──> Ragas Script ──> Measures Faithfulness ──> UI displays CI build pass/fail status
```
