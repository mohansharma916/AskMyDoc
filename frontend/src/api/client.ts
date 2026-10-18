import { SSEParser } from "./sse";

const BASE = `${(import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "")}/api/v1`;

// --- Types (mirror src/askdocs/api/schemas.py) --------------------------------

export interface Citation {
  n: number;
  chunk_id: string;
  doc_id: string;
  file_name: string;
  page: number | null;
  section_path: string[];
  snippet: string;
}

export interface AskResponse {
  query_id: string;
  question: string;
  answer: string;
  abstained: boolean;
  abstain_reason: string | null;
  citations: Citation[];
  usage: { input_tokens: number; output_tokens: number; cost_usd: number | null };
  latency_ms: Record<string, number>;
  model: string | null;
  prompt_version: string;
  trace_id?: string | null;
}

export interface DocumentInfo {
  doc_id: string;
  file_name: string;
  title: string;
  chunks: number;
  ingested_at: string;
}

export interface IngestJob {
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  files: number;
  counts: { indexed: number; updated: number; unchanged: number; failed: number; chunks: number };
  results: { doc_id: string; file_name: string; status: string; chunks: number; error: string | null }[];
  error: string | null;
}

export interface Health {
  status: "ok" | "degraded";
  database: boolean;
  qdrant: boolean;
  llm: { provider: string; model: string; configured: boolean };
  documents: number;
  chunks: number;
}

export type Rating = "helpful" | "not_helpful";

export interface RuntimeSettings {
  llm_provider: "anthropic" | "ollama";
  llm_model: string;
  llm_api_key_set: boolean;
  llm_effort: "low" | "medium" | "high" | "xhigh" | "max";
  llm_temperature: number;
  llm_timeout_s: number;
  ollama_url: string;
  rerank_model: string;
  prompt_version: string;
  chunk_size: number;
  chunk_overlap: number;
  retrieve_k: number;
  rerank_k: number;
  abstain_threshold: number;
  max_upload_mb: number;
}

/** PATCH body: any subset of the runtime settings; `llm_api_key` is write-only ("" clears it). */
export type SettingsUpdate = Partial<Omit<RuntimeSettings, "llm_api_key_set">> & { llm_api_key?: string };

export interface SettingsInfo {
  editable: boolean;
  settings: RuntimeSettings;
  defaults: RuntimeSettings;
  restart_required: Record<string, string | number | boolean>;
  prompt_versions: string[];
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

// --- REST ---------------------------------------------------------------------

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = body?.error ?? {};
    throw new ApiError(res.status, err.code ?? "internal_error", err.message ?? `Request failed (${res.status})`);
  }
  return body as T;
}

const json = (method: string, data: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

export const api = {
  health: () => request<Health>("/health"),
  documents: () => request<{ documents: DocumentInfo[] }>("/documents").then((r) => r.documents),
  deleteDocument: (docId: string) => request<void>(`/documents/${encodeURIComponent(docId)}`, { method: "DELETE" }),
  ingest: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<IngestJob>("/ingest", { method: "POST", body: form });
  },
  ingestJob: (jobId: string) => request<IngestJob>(`/ingest/${jobId}`),
  ask: (question: string, topK?: number) => request<AskResponse>("/ask", json("POST", { question, top_k: topK })),
  feedback: (queryId: string, rating: Rating) =>
    request<{ query_id: string; rating: Rating }>("/feedback", json("POST", { query_id: queryId, rating })),
  settings: () => request<SettingsInfo>("/settings"),
  updateSettings: (changes: SettingsUpdate) => request<SettingsInfo>("/settings", json("PATCH", changes)),
  resetSettings: () => request<SettingsInfo>("/settings/reset", { method: "POST" }),
};

// --- Streaming ----------------------------------------------------------------

export type StreamEvent =
  | { type: "meta"; query_id: string; trace_id?: string | null }
  | { type: "token"; text: string }
  | { type: "retry"; reason: string }
  | { type: "done"; result: AskResponse };

/** POST /ask/stream and yield parsed events until the stream ends or `signal` aborts. Omitting topK uses RERANK_K. */
export async function* streamAsk(question: string, signal?: AbortSignal, topK?: number): AsyncGenerator<StreamEvent> {
  const res = await fetch(`${BASE}/ask/stream`, { ...json("POST", { question, top_k: topK }), signal });
  if (!res.ok || !res.body) {
    const err = (await res.json().catch(() => ({})))?.error ?? {};
    throw new ApiError(res.status, err.code ?? "internal_error", err.message ?? `Request failed (${res.status})`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = new SSEParser();
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    for (const message of parser.push(decoder.decode(value, { stream: true }))) {
      const data = JSON.parse(message.data);
      if (message.event === "error") throw new ApiError(data.status ?? 500, data.code, data.message);
      if (message.event === "done") yield { type: "done", result: data as AskResponse };
      else if (message.event === "meta") yield { type: "meta", ...data };
      else if (message.event === "token") yield { type: "token", text: data.text };
      else if (message.event === "retry") yield { type: "retry", reason: data.reason };
    }
  }
}
