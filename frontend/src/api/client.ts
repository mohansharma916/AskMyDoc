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
  source_type?: "preloaded" | "user_upload";
}

export interface ChunkDetail {
  chunk_id: string;
  page: number | null;
  section_path: string[];
  text: string;
  token_count: number;
  position: number;
}

export interface DocumentDetail {
  doc_id: string;
  file_name: string;
  title: string;
  source_uri: string;
  source_type: "preloaded" | "user_upload";
  chunks: ChunkDetail[];
  chunk_count: number;
  full_text: string;
  has_file: boolean;
  file_url: string | null;
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

export type LLMProvider = "anthropic" | "openai" | "groq" | "ollama";

export interface RuntimeSettings {
  llm_provider: LLMProvider;
  llm_model: string;
  api_keys_set: Record<string, boolean>;
  llm_effort: "low" | "medium" | "high" | "xhigh" | "max";
  llm_temperature: number;
  llm_timeout_s: number;
  ollama_url: string;
  openai_base_url: string;
  rerank_model: string;
  prompt_version: string;
  chunk_size: number;
  chunk_overlap: number;
  retrieve_k: number;
  rerank_k: number;
  abstain_threshold: number;
  max_upload_mb: number;
}

/** Write-only setting holding each provider's API key ("" clears it). */
export const API_KEY_FIELDS = { anthropic: "llm_api_key", openai: "openai_api_key", groq: "groq_api_key" } as const;
type ApiKeyField = (typeof API_KEY_FIELDS)[keyof typeof API_KEY_FIELDS];

/** PATCH body: any subset of the runtime settings, plus write-only API keys. */
export type SettingsUpdate = Partial<Omit<RuntimeSettings, "api_keys_set">> & Partial<Record<ApiKeyField, string>>;

export interface SettingsInfo {
  editable: boolean;
  settings: RuntimeSettings;
  defaults: RuntimeSettings;
  restart_required: Record<string, string | number | boolean>;
  prompt_versions: string[];
}

export interface SessionInfo {
  session_id: string;
  expires_at: string;
  expires_in_s: number;
  ttl_s: number;
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

// --- Browser session ----------------------------------------------------------
// One private session per browser (localStorage is shared by its tabs). Every request
// carries the id; uploads are visible only to it and deleted when it expires.

const SESSION_KEY = "askdocs_session_id";
const expiredListeners = new Set<() => void>();

export const browserSession = {
  id(): string | null {
    try {
      return localStorage.getItem(SESSION_KEY);
    } catch {
      return null;
    }
  },
  set(id: string) {
    try {
      localStorage.setItem(SESSION_KEY, id);
    } catch {}
  },
  clear() {
    try {
      localStorage.removeItem(SESSION_KEY);
    } catch {}
  },
  /** Called whenever the server reports the session expired; returns an unsubscribe function. */
  onExpired(listener: () => void) {
    expiredListeners.add(listener);
    return () => void expiredListeners.delete(listener);
  },
};

/** Adds the session header; responses depend on it, so they must never come from the HTTP cache. */
function withSession(init?: RequestInit): RequestInit {
  const headers = new Headers(init?.headers);
  const id = browserSession.id();
  if (id) headers.set("X-Session-Id", id);
  return { ...init, headers, cache: "no-store" };
}

function toError(
  status: number,
  body: { error?: { code?: string; message?: string } } | null,
  init: RequestInit,
): ApiError {
  const err = body?.error ?? {};
  // A late reply about a session this browser already replaced must not end the new one.
  const sentId = new Headers(init.headers).get("X-Session-Id");
  if (err.code === "session_expired" && sentId === browserSession.id()) expiredListeners.forEach((l) => l());
  return new ApiError(status, err.code ?? "internal_error", err.message ?? `Request failed (${status})`);
}

// --- REST ---------------------------------------------------------------------

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const sent = withSession(init);
  const res = await fetch(`${BASE}${path}`, sent);
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw toError(res.status, body, sent);
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
  documentDetail: (docId: string) => request<DocumentDetail>(`/documents/${encodeURIComponent(docId)}`),
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
  createSession: () => request<SessionInfo>("/sessions", { method: "POST" }),
  currentSession: () => request<SessionInfo>("/sessions/current"),
  heartbeat: () => request<SessionInfo>("/sessions/current/heartbeat", { method: "POST" }),
  endSession: () => request<void>("/sessions/current", { method: "DELETE" }),
};

// --- Streaming ----------------------------------------------------------------

export type StreamEvent =
  | { type: "meta"; query_id: string; trace_id?: string | null }
  | { type: "token"; text: string }
  | { type: "retry"; reason: string }
  | { type: "done"; result: AskResponse };

/** POST /ask/stream and yield parsed events until the stream ends or `signal` aborts. Omitting topK uses RERANK_K. */
export async function* streamAsk(question: string, signal?: AbortSignal, topK?: number): AsyncGenerator<StreamEvent> {
  const sent = withSession({ ...json("POST", { question, top_k: topK }), signal });
  const res = await fetch(`${BASE}/ask/stream`, sent);
  if (!res.ok || !res.body) throw toError(res.status, await res.json().catch(() => ({})), sent);
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
