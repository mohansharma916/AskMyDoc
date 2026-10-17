import { useRef, useState } from "react";
import { api } from "../api.js";

const ACCEPT = ".pdf,.md,.markdown,.txt";

function StatusDot({ ok, label }) {
  return (
    <li className="status-item">
      <span className={`dot ${ok ? "ok" : "bad"}`} aria-hidden="true" />
      {label}
    </li>
  );
}

export default function DocumentPanel({ health, documents, onChange }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState(null);

  async function upload(files) {
    if (!files.length) return;
    setBusy(true);
    setMessage(null);
    try {
      const res = await api.upload(files);
      onChange(res.documents);
      const added = res.ingested.reduce((n, d) => n + d.chunks, 0);
      const errors = res.errors.map((e) => `${e.source}: ${e.error}`);
      setMessage({
        kind: errors.length ? "warn" : "ok",
        text: [`Indexed ${res.ingested.length} file(s), ${added} chunks.`, ...errors].join("\n"),
      });
    } catch (err) {
      setMessage({ kind: "error", text: err.message });
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function remove(source) {
    try {
      onChange((await api.deleteDocument(source)).documents);
    } catch (err) {
      setMessage({ kind: "error", text: err.message });
    }
  }

  async function reset() {
    if (!confirm("Remove every document from the index?")) return;
    try {
      onChange((await api.resetDocuments()).documents);
    } catch (err) {
      setMessage({ kind: "error", text: err.message });
    }
  }

  const totalChunks = documents.reduce((n, d) => n + d.chunks, 0);

  return (
    <aside className="sidebar">
      <header className="brand">
        <h1>Multi-Phase RAG</h1>
        <p>Ask your documents across three maturity phases.</p>
      </header>

      <section>
        <h2 className="section-title">Corpus</h2>
        <div
          className={`dropzone ${dragging ? "dragging" : ""} ${busy ? "busy" : ""}`}
          onClick={() => !busy && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            upload([...e.dataTransfer.files]);
          }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && inputRef.current?.click()}
        >
          <strong>{busy ? "Indexing…" : "Drop files or click to upload"}</strong>
          <span>PDF, Markdown, or text</span>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept={ACCEPT}
            hidden
            onChange={(e) => upload([...e.target.files])}
          />
        </div>
        {message && <p className={`notice ${message.kind}`}>{message.text}</p>}
      </section>

      <section className="doc-section">
        <div className="section-row">
          <h2 className="section-title">
            Indexed documents <span className="muted">({documents.length} · {totalChunks} chunks)</span>
          </h2>
          {documents.length > 0 && (
            <button className="link-button" onClick={reset}>
              Clear all
            </button>
          )}
        </div>
        {documents.length === 0 ? (
          <p className="muted small">Nothing indexed yet. Every phase searches the documents you upload here.</p>
        ) : (
          <ul className="doc-list">
            {documents.map((d) => (
              <li key={d.source}>
                <span className="doc-name" title={d.source}>
                  {d.source}
                </span>
                <span className="muted small">{d.chunks}</span>
                <button className="icon-button" aria-label={`Remove ${d.source}`} onClick={() => remove(d.source)}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="status">
        <h2 className="section-title">Backend</h2>
        {!health ? (
          <p className="muted small">Checking…</p>
        ) : health.offline ? (
          <p className="notice error">API unreachable (expected on :8001)</p>
        ) : (
          <ul className="status-list">
            <StatusDot ok={health.weaviate} label="Weaviate" />
            <StatusDot ok={health.anthropic_key} label={health.llm_model} />
            <StatusDot
              ok={health.reranker === "local" || health.cohere_key}
              label={health.reranker === "local" ? "Local re-ranker" : "Cohere re-ranker"}
            />
          </ul>
        )}
      </section>
    </aside>
  );
}
