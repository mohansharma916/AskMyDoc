import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { API_KEY_FIELDS, api, type LLMProvider, type SettingsInfo, type SettingsUpdate } from "../api/client";

const PROVIDERS: Record<LLMProvider, { label: string; models: string[] }> = {
  anthropic: { label: "Anthropic", models: ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"] },
  openai: { label: "OpenAI", models: ["gpt-5-mini", "gpt-5", "gpt-4.1", "gpt-4.1-mini"] },
  groq: { label: "Groq", models: ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "llama-3.1-8b-instant"] },
  ollama: { label: "Ollama", models: ["llama3.1"] },
};
const hasKey = (p: string): p is keyof typeof API_KEY_FIELDS => p in API_KEY_FIELDS;

const inputClass =
  "w-full rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900";

function SettingsForm({ info, onClose }: { info: SettingsInfo; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState<LLMProvider>(info.settings.llm_provider);
  const [model, setModel] = useState(info.settings.llm_model);
  const [apiKey, setApiKey] = useState("");
  const [saved, setSaved] = useState(false);

  const applied = (next: SettingsInfo) => {
    queryClient.setQueryData(["settings"], next);
    void queryClient.invalidateQueries({ queryKey: ["health"] });
    setProvider(next.settings.llm_provider);
    setModel(next.settings.llm_model);
    setApiKey("");
    setSaved(true);
  };
  const save = useMutation({ mutationFn: api.updateSettings, onSuccess: applied });
  const reset = useMutation({ mutationFn: api.resetSettings, onSuccess: applied });

  const pending: SettingsUpdate = {
    ...(provider !== info.settings.llm_provider ? { llm_provider: provider } : {}),
    ...(model.trim() !== info.settings.llm_model ? { llm_model: model.trim() } : {}),
    ...(apiKey && hasKey(provider) ? { [API_KEY_FIELDS[provider]]: apiKey } : {}),
  };
  const dirty = Object.keys(pending).length > 0;
  const busy = save.isPending || reset.isPending;
  const error = save.error ?? reset.error;
  const readOnly = !info.editable;

  const changeProvider = (p: LLMProvider) => {
    // Keep the saved model when switching back; otherwise suggest the new provider's default.
    setSaved(false);
    setProvider(p);
    setModel(p === info.settings.llm_provider ? info.settings.llm_model : PROVIDERS[p].models[0]);
    setApiKey("");
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (dirty) save.mutate(pending);
  };

  return (
    <form onSubmit={submit} className="flex min-h-0 flex-1 flex-col">
      <fieldset className="flex-1 space-y-4 overflow-y-auto px-5 py-4" disabled={readOnly || busy}>
        {readOnly && (
          <p className="rounded-md bg-amber-50 p-3 text-xs text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
            Editing is disabled on this server (DEV_SETTINGS_ENABLED=false).
          </p>
        )}

        <div>
          <label htmlFor="dev-provider" className="mb-1 block text-sm font-medium">
            Provider
          </label>
          <select
            id="dev-provider"
            value={provider}
            onChange={(e) => changeProvider(e.target.value as LLMProvider)}
            className={inputClass}
          >
            {(Object.keys(PROVIDERS) as LLMProvider[]).map((p) => (
              <option key={p} value={p}>
                {PROVIDERS[p].label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="dev-model" className="mb-1 block text-sm font-medium">
            Model
          </label>
          <input
            id="dev-model"
            required
            value={model}
            list="dev-models"
            onChange={(e) => {
              setSaved(false);
              setModel(e.target.value);
            }}
            className={inputClass}
          />
          <datalist id="dev-models">
            {PROVIDERS[provider].models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
          <p className="mt-1 text-xs text-slate-500">Pick a suggestion or type any model the provider offers.</p>
        </div>

        {hasKey(provider) && (
          <div>
            <label htmlFor="dev-api-key" className="mb-1 block text-sm font-medium">
              API key
            </label>
            <input
              id="dev-api-key"
              type="password"
              autoComplete="off"
              value={apiKey}
              placeholder={info.settings.api_keys_set[provider] ? "•••••••• (set — type to replace)" : "Not set"}
              onChange={(e) => {
                setSaved(false);
                setApiKey(e.target.value);
              }}
              className={inputClass}
            />
            <p className="mt-1 text-xs text-slate-500">
              Used only for {PROVIDERS[provider].label}. The server never sends it back.
            </p>
          </div>
        )}
      </fieldset>

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
        <p className="mt-2 text-[11px] text-slate-500 dark:text-slate-400">Changes live in server memory and reset when the API restarts.</p>
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
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab" && panel.current) {
        const focusable = panel.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };
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
          <h2 id="dev-settings-title" className="font-semibold text-slate-900 dark:text-slate-100">
            Developer settings
          </h2>
          <button
            type="button"
            aria-label="Close developer settings"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200 transition"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
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
