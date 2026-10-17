import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import { PHASES } from "./phases.js";
import DocumentPanel from "./components/DocumentPanel.jsx";
import QueryPanel from "./components/QueryPanel.jsx";
import EvaluationPanel from "./components/EvaluationPanel.jsx";
import PipelineStrip from "./components/PipelineStrip.jsx";

export default function App() {
  const [phase, setPhase] = useState(1);
  const [health, setHealth] = useState(null);
  const [documents, setDocuments] = useState([]);
  // Results are kept per phase so switching tabs never loses an answer.
  const [results, setResults] = useState({ 1: null, 2: null, 3: null });

  const refreshDocuments = useCallback(() => {
    api.documents().then((d) => setDocuments(d.documents)).catch(() => setDocuments([]));
  }, []);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ offline: true }));
    refreshDocuments();
  }, [refreshDocuments]);

  const current = PHASES.find((p) => p.id === phase);
  const setResult = (r) => setResults((prev) => ({ ...prev, [phase]: r }));

  return (
    <div className="layout">
      <DocumentPanel health={health} documents={documents} onChange={setDocuments} />

      <main className="main">
        <nav className="tabs" role="tablist">
          {PHASES.map((p) => (
            <button
              key={p.id}
              role="tab"
              aria-selected={p.id === phase}
              className={`tab ${p.id === phase ? "active" : ""}`}
              onClick={() => setPhase(p.id)}
            >
              <span className="tab-label">{p.label}</span>
              <span className="tab-title">{p.title}</span>
              <span className="tab-subtitle">{p.subtitle}</span>
            </button>
          ))}
        </nav>

        <section className="phase-header">
          <p>{current.description}</p>
          <PipelineStrip steps={current.pipeline} />
        </section>

        {phase === 3 && <EvaluationPanel />}
        <QueryPanel
          key={phase}
          phase={phase}
          result={results[phase]}
          onResult={setResult}
          hasDocuments={documents.length > 0}
        />
      </main>
    </div>
  );
}
