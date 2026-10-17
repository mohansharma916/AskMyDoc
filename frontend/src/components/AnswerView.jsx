import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api.js";
import PipelineStrip from "./PipelineStrip.jsx";

// Turn "[2]" markers into links the custom renderer shows as citation chips.
const linkCitations = (text) => text.replace(/\[(\d+)\](?!\()/g, "[$1](#cite-$1)");

function scoreClass(v) {
  if (v === null || v === undefined) return "";
  return v >= 0.8 ? "good" : v >= 0.5 ? "fair" : "poor";
}

function PromptViewer({ name, version }) {
  const [open, setOpen] = useState(false);
  const [prompt, setPrompt] = useState(null);

  useEffect(() => {
    if (open && !prompt) api.prompts().then((p) => setPrompt(p[name])).catch(() => {});
  }, [open, prompt, name]);

  return (
    <details className="prompt-viewer" onToggle={(e) => setOpen(e.currentTarget.open)}>
      <summary>
        Prompt <code>{name}</code> · v{version}
      </summary>
      {prompt ? (
        <pre>
          <strong>system</strong>
          {"\n" + prompt.system}
          <strong>user</strong>
          {"\n" + prompt.user}
        </pre>
      ) : (
        <p className="muted small">Loading…</p>
      )}
    </details>
  );
}

export default function AnswerView({ result }) {
  const [active, setActive] = useState(null);
  const cited = result.citations.filter((c) => c.cited);
  const shown = result.declined || cited.length === 0 ? result.citations : cited;

  return (
    <div className="answer">
      <div className={`answer-body ${result.declined ? "declined" : ""}`}>
        {result.declined && <span className="badge warn">Declined</span>}
        {result.faithfulness !== null && result.faithfulness !== undefined && (
          <span className={`badge score ${scoreClass(result.faithfulness)}`}>
            Faithfulness {result.faithfulness.toFixed(2)}
          </span>
        )}
        <ReactMarkdown
          components={{
            a: ({ href, children }) => {
              const match = href?.match(/^#cite-(\d+)$/);
              if (!match) return <a href={href} target="_blank" rel="noreferrer">{children}</a>;
              const n = Number(match[1]);
              return (
                <button
                  type="button"
                  className={`cite-chip ${active === n ? "active" : ""}`}
                  onMouseEnter={() => setActive(n)}
                  onMouseLeave={() => setActive(null)}
                  onClick={() => document.getElementById(`source-${n}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" })}
                >
                  {n}
                </button>
              );
            },
          }}
        >
          {linkCitations(result.answer)}
        </ReactMarkdown>
        {result.decline_reason && <p className="muted small">Reason: {result.decline_reason}</p>}
      </div>

      {result.prompt_name && result.phase !== 1 && (
        <PromptViewer name={result.prompt_name} version={result.prompt_version} />
      )}

      <h3 className="sub-title">What ran</h3>
      <PipelineStrip trace={result.trace} />

      {shown.length > 0 && (
        <>
          <h3 className="sub-title">
            {result.declined ? "Passages considered" : cited.length ? "Cited sources" : "Retrieved passages"}
          </h3>
          <ol className="sources">
            {shown.map((c) => (
              <li
                key={c.id}
                id={`source-${c.index}`}
                className={`source ${active === c.index ? "active" : ""}`}
              >
                <div className="source-head">
                  <span className="cite-chip static">{c.index}</span>
                  <span className="source-name">
                    {c.source}
                    {c.page ? ` · p.${c.page}` : ""}
                  </span>
                  <span className="muted small">
                    score {c.score?.toFixed(3)}
                    {c.retrieval_score !== undefined && ` · retrieval ${c.retrieval_score.toFixed(3)}`}
                  </span>
                </div>
                <p className="source-text">{c.text}</p>
              </li>
            ))}
          </ol>
        </>
      )}
    </div>
  );
}
