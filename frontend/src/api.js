const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return body;
}

const json = (method, data) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

function filesForm(field, files) {
  const form = new FormData();
  for (const f of files) form.append(field, f);
  return { method: "POST", body: form };
}

export const api = {
  health: () => request("/health"),
  documents: () => request("/documents"),
  upload: (files) => request("/upload", filesForm("files", files)),
  deleteDocument: (source) => request(`/documents/${encodeURIComponent(source)}`, { method: "DELETE" }),
  resetDocuments: () => request("/documents", { method: "DELETE" }),
  query: (question, phase) => request("/query", json("POST", { question, phase_target: phase })),
  prompts: () => request("/prompts"),
  golden: () => request("/golden"),
  uploadGolden: (file) => request("/golden", filesForm("file", [file])),
  startEvaluation: (pipelinePhase, limit) =>
    request("/evaluate", json("POST", { pipeline_phase: pipelinePhase, limit: limit || null })),
  evaluationStatus: (id) => request(`/evaluate/${id}`),
  evaluationHistory: () => request("/evaluate/history"),
};
