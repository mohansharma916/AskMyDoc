export const PHASES = [
  {
    id: 1,
    label: "Phase 1",
    title: "Fundamentals",
    subtitle: "The Basic RAG",
    description: "Vector-based semantic search over your chunks, then an answer that cites its sources.",
    pipeline: ["Vector search", "Top K chunks", "Base prompt", "LLM", "Response"],
  },
  {
    id: 2,
    label: "Phase 2",
    title: "Production Quality",
    subtitle: "The Resilient RAG",
    description:
      "Hybrid BM25 + vector retrieval, cross-encoder re-ranking, and a guardrail that declines when the documents don't support an answer.",
    pipeline: ["Hybrid search", "Re-ranker", "Citation guardrail", "Versioned prompt", "LLM", "Response"],
  },
  {
    id: 3,
    label: "Phase 3",
    title: "Shippable System",
    subtitle: "The Evaluated RAG",
    description:
      "Measure the pipeline against a golden dataset with Ragas and gate the build on quality thresholds, the way CI would.",
    pipeline: ["Golden dataset", "Pipeline answers", "Ragas metrics", "Quality gates", "Build status"],
  },
];
