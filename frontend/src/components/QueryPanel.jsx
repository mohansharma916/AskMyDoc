import { useState } from "react";
import { api } from "../api.js";
import AnswerView from "./AnswerView.jsx";

const PLACEHOLDERS = {
  1: "Ask a question about your documents…",
  2: "Ask a question — this pipeline declines if your documents can't support the answer…",
  3: "Ask a question and get a live Ragas faithfulness score for the answer…",
};

export default function QueryPanel({ phase, result, onResult, hasDocuments }) {
  const [question, setQuestion] = useState(result?.question ?? "");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function submit(e) {
    e.preventDefault();
    if (!question.trim() || loading) return;
    setLoading(true);
    setError(null);
    try {
      onResult(await api.query(question.trim(), phase));
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="card">
      {phase === 3 && <h2 className="card-title">Live query with faithfulness scoring</h2>}
      <form className="query-form" onSubmit={submit}>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
          }}
          placeholder={PLACEHOLDERS[phase]}
          rows={3}
        />
        <div className="form-row">
          <span className="muted small">
            {hasDocuments ? "⌘/Ctrl + Enter to send" : "Upload documents in the sidebar first."}
          </span>
          <button className="primary" type="submit" disabled={loading || !question.trim()}>
            {loading ? "Running pipeline…" : `Ask with Phase ${phase}`}
          </button>
        </div>
      </form>
      {error && <p className="notice error">{error}</p>}
      {result && !loading && <AnswerView result={result} />}
    </section>
  );
}
