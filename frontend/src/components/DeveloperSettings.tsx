import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { api, type RuntimeSettings, type SettingsInfo, type SettingsUpdate } from "../api/client";

type Key = Exclude<keyof RuntimeSettings, "llm_api_key_set">;
type Draft = Record<Key, string>;

interface Field {
  key: Key;
  label: string;
  help: string;
  kind: "text" | "number" | "select";
  options?: string[];
  min?: number;
  max?: number;
  step?: number;
  when?: (d: Draft) => boolean;
}

const MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"];

const SECTIONS: { title: string; note?: string; fields: Field[] }[] = [
  {
    title: "Language model",
    fields: [
      { key: "llm_provider", label: "Provider", help: "Claude via the Anthropic API, or a local Ollama model.", kind: "select", options: ["anthropic", "ollama"] },
      { key: "llm_model", label: "Model", help: "Model id, e.g. claude-opus-5-5 or llama3.1.", kind: "text" },
      {
        key: "llm_effort",
        label: "Effort",
        help: "How much the model thinks before answering. Higher is slower and costlier.",
        kind: "select",
        options: ["low", "medium", "high", "xhigh", "max"],
        when: (d) => d.llm_provider === "anthropic",
      },
      {
        key: "llm_temperature",
        label: "Temperature",
        help: "Sampling temperature (Ollama only).",
        kind: "number",
        min: 0,
        max: 2,
        step: 0.05,
        when: (d) => d.llm_provider === "ollama",
      },
      { key: "ollama_url", label: "Ollama URL", help: "Base URL of the Ollama server.", kind: "text", when: (d) => d.llm_provider === "ollama" },
      { key: "llm_timeout_s", label: "Timeout (s)", help: "Per-request LLM timeout.", kind: "number", min: 1, max: 600, step: 1 },
    ],
  },
  {
    title: "Prompt",
    fields: [{ key: "prompt_version", label: "Prompt version", help: "File in prompts/ used as the system prompt.", kind: "select" }],
  },
  {
    title: "Retrieval",
    fields: [
      { key: "retrieve_k", label: "Retrieve k", help: "Candidates fetched by hybrid search before reranking.", kind: "number", min: 1, max: 100, step: 1 },
      { key: "rerank_k", label: "Rerank k", help: "Top reranked chunks shown to the LLM. Must be ≤ retrieve k.", kind: "number", min: 1, max: 20, step: 1 },
      {
        key: "abstain_threshold",
        label: "Abstain threshold",
        help: "Minimum best rerank score (0–1) needed to answer; below it the app says “not found”.",
        kind: "number",
        min: 0,
        max: 1,
        step: 0.01,
      },
      { key: "rerank_model", label: "Reranker model", help: "Cross-encoder; a new one downloads and loads on the next question.", kind: "text" },
    ],
  },
  {
    title: "Ingestion",
    note: "Applies to documents indexed after the change. Already-indexed files keep their chunks until they change.",
    fields: [
      { key: "chunk_size", label: "Chunk size (tokens)", help: "Target tokens per chunk.", kind: "number", min: 64, max: 4096, step: 1 },
      { key: "chunk_overlap", label: "Chunk overlap (tokens)", help: "Tokens shared between neighbouring chunks.", kind: "number", min: 0, max: 1024, step: 1 },
      { key: "max_upload_mb", label: "Max upload (MB)", help: "Largest file accepted by the upload box.", kind: "number", min: 1, max: 500, step: 1 },
    ],
  },
];

const FIELDS = SECTIONS.flatMap((s) => s.fields);

const toDraft = (s: RuntimeSettings): Draft =>
  Object.fromEntries(FIELDS.map((f) => [f.key, String(s[f.key])])) as Draft;

const parse = (f: Field, value: string) => (f.kind === "number" ? Number(value) : value.trim());

/** Only the fields that differ from what the server has. */
function changes(draft: Draft, current: RuntimeSettings): SettingsUpdate {
  const out: Record<string, string | number> = {};
  for (const f of FIELDS) {
    const value = parse(f, draft[f.key]);
    if (value !== current[f.key]) out[f.key] = value;
  }
  return out as SettingsUpdate;
}

const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900";

function SettingsForm({ info, onClose }: { info: SettingsInfo; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(() => toDraft(info.settings));
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);

  const applied = (next: SettingsInfo) => {
    queryClient.setQueryData(["settings"], next);
    void queryClient.invalidateQueries({ queryKey: ["health"] });
    setDraft(toDraft(next.settings));
    setApiKey("");
    setSaved(true);
  };
  const save = useMutation({ mutationFn: api.updateSettings, onSuccess: applied });
  const reset = useMutation({ mutationFn: api.resetSettings, onSuccess: applied });

  const pending: SettingsUpdate = { ...changes(draft, info.settings), ...(apiKey ? { llm_api_key: apiKey } : {}) };
  const dirty = Object.keys(pending).length > 0;
  const busy = save.isPending || reset.isPending;
  const error = save.error ?? reset.error;
  const readOnly = !info.editable;

  const set = (key: Key, value: string) => {
    setSaved(false);
    setDraft((d) => ({ ...d, [key]: value }));
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (dirty) save.mutate(pending);
  };

  return (
    <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 space-y-6 overflow-y-auto px-5 py-4">
        {readOnly && (
          <p className="rounded-md bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
            Editing is disabled on this server (DEV_SETTINGS_ENABLED=false).
          </p>
        )}

        {SECTIONS.map((section) => (
          <fieldset key={section.title} className="space-y-3" disabled={readOnly || busy}>
            <legend className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">{section.title}</legend>
            {section.note && <p className="text-xs text-slate-500">{section.note}</p>}

            {section.fields
              .filter((f) => !f.when || f.when(draft))
              .map((f) => {
                const id = `dev-${f.key}`;
                const modified = parse(f, draft[f.key]) !== info.defaults[f.key];
                const options = f.key === "prompt_version" ? info.prompt_versions : f.options;
                return (
                  <div key={f.key}>
                    <label htmlFor={id} className="mb-1 flex items-center gap-1.5 text-sm font-medium">
                      {f.label}
                      {modified && (
                        <span title={`Default: ${info.defaults[f.key]}`} className="text-xs font-normal text-indigo-600 dark:text-indigo-400">
                          · changed
                        </span>
                      )}
                    </label>
                    {f.kind === "select" ? (
                      <select id={id} value={draft[f.key]} onChange={(e) => set(f.key, e.target.value)} className={inputClass}>
                        {options?.map((o) => (
                          <option key={o} value={o}>
                            {o}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        id={id}
                        type={f.kind}
                        required
                        min={f.min}
                        max={f.max}
                        step={f.step}
                        value={draft[f.key]}
                        list={f.key === "llm_model" && draft.llm_provider === "anthropic" ? "dev-models" : undefined}
                        onChange={(e) => set(f.key, e.target.value)}
                        className={inputClass}
                      />
                    )}
                    <p className="mt-1 text-xs text-slate-500">{f.help}</p>
                  </div>
                );
              })}

            {section.title === "Language model" && draft.llm_provider === "anthropic" && (
              <div>
                <label htmlFor="dev-llm_api_key" className="mb-1 block text-sm font-medium">
                  API key
                </label>
                <input
                  id="dev-llm_api_key"
                  type="password"
                  autoComplete="off"
                  value={apiKey}
                  placeholder={info.settings.llm_api_key_set ? "•••••••• (set — type to replace)" : "Not set — uses ANTHROPIC_API_KEY"}
                  onChange={(e) => {
                    setSaved(false);
                    setApiKey(e.target.value);
                  }}
                  className={inputClass}
                />
                <p className="mt-1 text-xs text-slate-500">Write-only: the server never sends the key back.</p>
              </div>
            )}
          </fieldset>
        ))}
        <datalist id="dev-models">
          {MODELS.map((m) => (
            <option key={m} value={m} />
          ))}
        </datalist>

        <section>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">Restart required</h3>
          <p className="mb-2 text-xs text-slate-500">Change these in .env and restart the API.</p>
          <dl className="space-y-1 text-xs">
            {Object.entries(info.restart_required).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3">
                <dt className="font-mono text-slate-500">{k.toUpperCase()}</dt>
                <dd className="truncate font-mono" title={String(v)}>
                  {String(v)}
                </dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      <footer className="border-t border-slate-200 px-5 py-3 dark:border-slate-800">
        <div aria-live="polite" className="mb-2 min-h-4 text-xs">
          {error && (
            <p role="alert" className="text-red-600">
              {error.message}
            </p>
          )}
          {saved && !dirty && !error && <p className="text-emerald-700 dark:text-emerald-400">Saved. Applies to the next question.</p>}
        </div>
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            disabled={readOnly || busy}
            onClick={() => reset.mutate()}
            className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 disabled:opacity-50 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Reset to defaults
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
            >
              Close
            </button>
            <button
              type="submit"
              disabled={readOnly || busy || !dirty}
              className="rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {save.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
        <p className="mt-2 text-[11px] text-slate-400">Changes live in server memory and reset when the API restarts.</p>
      </footer>
    </form>
  );
}

export default function DeveloperSettings({ open, onClose }: { open: boolean; onClose: () => void }) {
  const panel = useRef<HTMLDivElement>(null);
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings, enabled: open, refetchOnWindowFocus: false });

  useEffect(() => {
    if (!open) return;
    panel.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div aria-hidden className="absolute inset-0 bg-slate-900/30 backdrop-blur-[1px]" onClick={onClose} />
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dev-settings-title"
        tabIndex={-1}
        className="relative flex h-full w-full max-w-md flex-col border-l border-slate-200 bg-white shadow-xl outline-none dark:border-slate-800 dark:bg-slate-900"
      >
        <header className="flex items-center justify-between border-b border-slate-200 px-5 py-3 dark:border-slate-800">
          <h2 id="dev-settings-title" className="font-semibold">
            Developer settings
          </h2>
          <button
            type="button"
            aria-label="Close developer settings"
            onClick={onClose}
            className="rounded px-2 text-lg text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800"
          >
            ×
          </button>
        </header>
        {settings.isPending && <p className="p-5 text-sm text-slate-500">Loading settings…</p>}
        {settings.isError && (
          <p role="alert" className="p-5 text-sm text-red-600">
            Could not load settings: {settings.error.message}
          </p>
        )}
        {settings.data && <SettingsForm info={settings.data} onClose={onClose} />}
      </div>
    </div>
  );
}
