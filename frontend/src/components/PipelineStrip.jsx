export default function PipelineStrip({ steps, trace }) {
  // With a trace, show what actually ran (and timings); otherwise the planned path.
  const items = trace
    ? trace.map((t) => ({ label: t.step, detail: t.detail, ms: t.ms }))
    : steps.map((s) => ({ label: s }));

  return (
    <ol className={`pipeline ${trace ? "pipeline-trace" : ""}`}>
      {items.map((item, i) => (
        <li key={i} className="pipeline-step" title={item.detail}>
          <span className="pipeline-label">{item.label}</span>
          {item.ms !== undefined && <span className="pipeline-ms">{item.ms} ms</span>}
          {item.detail && <span className="pipeline-detail">{item.detail}</span>}
        </li>
      ))}
    </ol>
  );
}
