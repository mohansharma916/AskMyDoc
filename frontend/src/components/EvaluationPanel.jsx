import { useEffect, useRef, useState } from "react";
import { api } from "../api.js";

const METRIC_LABELS = {
  faithfulness: "Faithfulness",
  answer_relevancy: "Answer relevancy",
  context_recall: "Context recall",
};
const STATUS_LABELS = {
  queued: "Queued",
  answering: "Running pipeline on golden questions",
  scoring: "Scoring with Ragas",
};

const fmt = (v) => (v === null || v === undefined ? "—" : v.toFixed(2));

function MetricGauge({ name, metric }) {
  const pct = Math.max(0, Math.min(1, metric.value ?? 0)) * 100;
  return (
    <div className={`metric ${metric.passed ? "pass" : "fail"}`}>
      <div className="metric-head">
        <span>{METRIC_LABELS[name] ?? name}</span>
        <span className="metric-status">{metric.passed ? "PASS" : "FAIL"}</span>
      </div>
      <div className="metric-value">{fmt(metric.value)}</div>
      <div className="bar">
        <div className="bar-fill" style={{ width: `${pct}%` }} />
        <div className="bar-threshold" style={{ left: `${metric.threshold * 100}%` }} title={`Threshold ${metric.threshold}`} />
      </div>
      <div className="muted small">Threshold ≥ {metric.threshold}</div>
    </div>
  );
}

function GoldenDataset({ golden, onUpload }) {
  const inputRef = useRef(null);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);

  async function upload(file) {
    if (!file) return;
    setError(null);
    try {
      onUpload(await api.uploadGolden(file));
    } catch (err) {
      setError(err.message);
    } finally {
      inputRef.current.value = "";
    }
  }

  const items = golden?.items ?? [];
  const visible = expanded ? items : items.slice(0, 5);

  return (
    <div className="card">
      <div className="section-row">
        <h2 className="card-title">Golden dataset</h2>
        <button className="secondary" onClick={() => inputRef.current.click()}>
          {items.length ? "Replace dataset" : "Upload dataset"}
        </button>
        <input ref={inputRef} type="file" accept=".json,.csv" hidden onChange={(e) => upload(e.target.files[0])} />
      </div>
      <p className="muted small">
        JSON list or CSV with <code>question</code> and <code>ground_truth</code> (or <code>answer</code>) columns.
        Aim for 50–200 manually verified pairs.
      </p>
      {error && <p className="notice error">{error}</p>}
      {golden?.warning && <p className="notice warn">{golden.warning}</p>}
      {items.length > 0 && (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>#</th>
                <th>Question</th>
                <th>Ground truth</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((i) => (
                <tr key={i.id}>
                  <td className="muted">{i.id}</td>
                  <td>{i.question}</td>
                  <td>{i.ground_truth}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {items.length > 5 && (
            <button className="link-button" onClick={() => setExpanded(!expanded)}>
              {expanded ? "Show fewer" : `Show all ${items.length} pairs`}
            </button>
          )}
        </>
      )}
    </div>
  );
}

function BuildResult({ build }) {
  const [showRows, setShowRows] = useState(false);
  return (
    <div className="build">
      <div className={`build-banner ${build.passed ? "pass" : "fail"}`}>
        <span className="build-icon" aria-hidden="true">{build.passed ? "✓" : "✕"}</span>
        <div>
          <strong>
            Build #{build.build_number} {build.passed ? "passed" : "failed"}
          </strong>
          <div className="small">
            Phase {build.pipeline_phase} pipeline · {build.samples} samples · {build.duration_s}s
          </div>
        </div>
      </div>
      <div className="metrics">
        {Object.entries(build.metrics).map(([name, m]) => (
          <MetricGauge key={name} name={name} metric={m} />
        ))}
      </div>
      {build.rows && (
        <>
          <button className="link-button" onClick={() => setShowRows(!showRows)}>
            {showRows ? "Hide per-question scores" : "Show per-question scores"}
          </button>
          {showRows && (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Question</th>
                    <th>Answer</th>
                    <th>Faith.</th>
                    <th>Relev.</th>
                    <th>Recall</th>
                  </tr>
                </thead>
                <tbody>
                  {build.rows.map((r) => (
                    <tr key={r.id}>
                      <td>{r.question}</td>
                      <td className={r.declined ? "muted" : ""}>{r.declined ? "(declined)" : r.answer}</td>
                      <td>{fmt(r.faithfulness)}</td>
                      <td>{fmt(r.answer_relevancy)}</td>
                      <td>{fmt(r.context_recall)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function EvaluationPanel() {
  const [golden, setGolden] = useState(null);
  const [history, setHistory] = useState({ builds: [], thresholds: {} });
  const [pipelinePhase, setPipelinePhase] = useState(2);
  const [limit, setLimit] = useState("");
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);

  const loadHistory = () => api.evaluationHistory().then(setHistory).catch(() => {});

  useEffect(() => {
    api.golden().then(setGolden).catch(() => {});
    loadHistory();
  }, []);

  // Poll the running job until it finishes.
  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") return;
    const timer = setInterval(async () => {
      try {
        const next = await api.evaluationStatus(job.id);
        setJob(next);
        if (next.status === "completed") loadHistory();
      } catch (err) {
        setError(err.message);
        setJob(null);
      }
    }, 1500);
    return () => clearInterval(timer);
  }, [job]);

  async function run() {
    setError(null);
    try {
      setJob(await api.startEvaluation(pipelinePhase, Number(limit) || null));
    } catch (err) {
      setError(err.message);
    }
  }

  const running = job && !["completed", "failed"].includes(job.status);
  const lastBuild = job?.result ?? history.builds.at(-1);

  return (
    <>
      <GoldenDataset golden={golden} onUpload={setGolden} />

      <div className="card">
        <h2 className="card-title">CI quality gate</h2>
        <div className="run-controls">
          <label>
            Pipeline under test
            <select value={pipelinePhase} onChange={(e) => setPipelinePhase(Number(e.target.value))} disabled={running}>
              <option value={2}>Phase 2 · Resilient RAG</option>
              <option value={1}>Phase 1 · Basic RAG</option>
            </select>
          </label>
          <label>
            Sample limit
            <input
              type="number"
              min="1"
              placeholder="All"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              disabled={running}
            />
          </label>
          <button className="primary" onClick={run} disabled={running || !golden?.items?.length}>
            {running ? "Running…" : "Run evaluation"}
          </button>
        </div>

        {error && <p className="notice error">{error}</p>}
        {running && (
          <div className="progress">
            <div className="progress-label">
              {STATUS_LABELS[job.status]}
              {job.status === "answering" && ` (${job.progress.done}/${job.progress.total})`}
            </div>
            <div className="bar">
              <div
                className={`bar-fill ${job.status === "scoring" ? "indeterminate" : ""}`}
                style={{ width: `${job.progress.total ? (job.progress.done / job.progress.total) * 100 : 0}%` }}
              />
            </div>
          </div>
        )}
        {job?.status === "failed" && <p className="notice error">Build errored: {job.error}</p>}
        {!running && lastBuild && <BuildResult build={lastBuild} />}
        {!running && !lastBuild && <p className="muted small">No builds yet. Upload a golden dataset and run an evaluation.</p>}

        {history.builds.length > 0 && (
          <>
            <h3 className="sub-title">Build history</h3>
            <ul className="history">
              {[...history.builds].reverse().map((b) => (
                <li key={b.id} className={b.passed ? "pass" : "fail"}>
                  <span className="history-status">{b.passed ? "✓" : "✕"}</span>
                  <span>#{b.build_number}</span>
                  <span className="muted">Phase {b.pipeline_phase}</span>
                  {Object.entries(b.metrics).map(([k, m]) => (
                    <span key={k} className={`muted small ${m.passed ? "" : "fail-text"}`}>
                      {METRIC_LABELS[k]?.split(" ")[0]} {fmt(m.value)}
                    </span>
                  ))}
                  <span className="muted small history-time">{new Date(b.finished_at).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </>
  );
}
