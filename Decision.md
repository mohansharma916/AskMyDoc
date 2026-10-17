# Architecture Decisions

## Context

We need to build a single application with a unified backend but a multi-modal frontend that processes queries through three different architectural paths depending on the selected phase.

## Architecture Decision Records (ADRs)

| ADR ID | Area | Decision | Rationale |
|--------|------|----------|-----------|
| ADR 1 | Vector Database | Weaviate | Native support for hybrid search (combining BM25 and vector search) out-of-the-box. Significantly reduces custom engineering for Phase 2 requirements compared to ChromaDB. |
| ADR 2 | Orchestration | LangChain & LangGraph | Recommended for handling complex, multi-step RAG pipelines. LangGraph routes queries to the correct execution path based on the frontend selection. |
| ADR 3 | Re-ranker | Cohere | Provides a robust, managed cross-encoder re-ranking API. Simpler to implement for Phase 2 than hosting custom Sentence Transformers, with abstract architecture allowing future swapping. |
| ADR 4 | Evaluation | Ragas | Specifically designed to measure faithfulness and ensure claims in generated answers are supported by retrieved chunks. |
| ADR 5 | Web Frameworks | React + FastAPI | FastAPI (Python) integrates smoothly with LangChain, Weaviate, Cohere, and Ragas. React enables a stateful UI where document upload stays static while phase sections update dynamically. |
