# Product Requirements Document

**Product Name:** Multi-Phase RAG Demonstrator

**Objective:** Build a domain-specific "ask my doc" application that visually and functionally bridges the gap between a basic RAG demo and a production-ready system by allowing users to toggle between three distinct maturity phases.

## 1. User Interface Structure

- **Common Document Upload:** A persistent top or sidebar section where users upload their corpus (PDFs, Markdown, etc.). Documents uploaded here populate the shared vector backend.
- **Phase Selection:** A three-tab or three-column layout allowing the user to select which pipeline executes their query.

## 2. Feature Specifications by Phase

### Phase 1: Fundamentals (The Basic RAG)

**Description:** Demonstrates the baseline capabilities of vector-based semantic search.

- **Ingestion & Chunking:** Processes uploaded documents into chunks of 500–800 tokens with approximately 100 tokens of overlap to preserve context boundaries.
- **Storage:** Stores embeddings in a vector database (Chroma or Weaviate).
- **Retrieval Pipeline:** Executes a standard semantic search, pulling the top K most relevant chunks and generating an answer that cites the exact source.

### Phase 2: Production Quality (The Resilient RAG)

**Description:** Introduces advanced retrieval strategies and strict hallucination guardrails.

- **Hybrid Retrieval:** Combines traditional BM25 keyword search with the vector-based semantic search from Phase 1.
- **Re-ranking:** Passes the initially retrieved chunks through a cross-encoder re-ranker to accurately evaluate and rescore the query-chunk pairs.
- **Citation Enforcement:** The system strictly declines to answer if the retrieved chunks do not contain the necessary information to support a response.
- **Configuration Visibility:** UI optionally displays the specific versioned prompt used from the configuration file.

### Phase 3: Shippable System (The Evaluated RAG)

**Description:** Exposes the evaluation and continuous integration mechanics typically hidden in the backend.

- **Golden Dataset Management:** Allows users to upload or view a "golden evaluation dataset" consisting of 50–200 manually verified question-answer pairs.
- **Live Evaluation Run:** Users can trigger an evaluation script using the Ragas framework to measure the "faithfulness" of the system (verifying if generated answers are truly supported by the retrieved chunks).
- **CI/CD Simulation:** The UI displays a dashboard showing whether the current build passes or fails based on quality thresholds, mimicking a Continuous Integration pipeline.
