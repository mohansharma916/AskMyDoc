import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import AnswerView from "./components/AnswerView";
import AskBox from "./components/AskBox";
import CitationPanel from "./components/CitationPanel";
import DeveloperSettings from "./components/DeveloperSettings";
import Feedback from "./components/Feedback";
import NotFoundState from "./components/NotFoundState";
import UploadPanel from "./components/UploadPanel";
import { useAskStream } from "./hooks/useAskStream";

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
  const ask = useAskStream();
  const [active, setActive] = useState<number | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const closeSettings = useCallback(() => setSettingsOpen(false), []);

  const result = ask.result;
  const citations = result?.citations ?? [];
  useEffect(() => setActive(result?.citations[0]?.n ?? null), [result]);

  const streaming = ask.status === "streaming";
  const abstained = result?.abstained ?? false;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-slate-900">
        <h1 className="text-lg font-semibold">Ask My Docs</h1>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-2 text-xs text-slate-500">
            <span
              aria-hidden
              className={`h-2 w-2 rounded-full ${
                health.data?.status === "ok" ? "bg-emerald-500" : health.isError ? "bg-red-500" : "bg-amber-500"
              }`}
            />
            {health.data
              ? `${health.data.documents} documents · ${health.data.chunks} chunks · ${health.data.llm.model}`
              : health.isError
                ? "API unreachable"
                : "Connecting…"}
          </span>
          <button
            type="button"
            aria-haspopup="dialog"
            aria-expanded={settingsOpen}
            onClick={() => setSettingsOpen(true)}
            className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            <svg aria-hidden viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
              <path
                fillRule="evenodd"
                d="M8.34 1.8A1 1 0 0 1 9.32 1h1.36a1 1 0 0 1 .98.8l.28 1.4a7 7 0 0 1 1.62.94l1.36-.46a1 1 0 0 1 1.18.45l.68 1.18a1 1 0 0 1-.2 1.25l-1.07.95a7 7 0 0 1 0 1.88l1.07.95a1 1 0 0 1 .2 1.25l-.68 1.18a1 1 0 0 1-1.18.45l-1.36-.46a7 7 0 0 1-1.62.94l-.28 1.4a1 1 0 0 1-.98.8H9.32a1 1 0 0 1-.98-.8l-.28-1.4a7 7 0 0 1-1.62-.94l-1.36.46a1 1 0 0 1-1.18-.45l-.68-1.18a1 1 0 0 1 .2-1.25l1.07-.95a7 7 0 0 1 0-1.88l-1.07-.95a1 1 0 0 1-.2-1.25l.68-1.18a1 1 0 0 1 1.18-.45l1.36.46a7 7 0 0 1 1.62-.94l.28-1.4ZM10 13a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z"
                clipRule="evenodd"
              />
            </svg>
            Developer settings
          </button>
        </div>
      </header>
      <DeveloperSettings open={settingsOpen} onClose={closeSettings} />

      <div className="mx-auto grid w-full max-w-7xl flex-1 gap-6 p-6 lg:grid-cols-[260px_minmax(0,1fr)_340px]">
        <div className="lg:border-r lg:border-slate-200 lg:pr-6 lg:dark:border-slate-800">
          <UploadPanel />
        </div>

        <main className="flex min-w-0 flex-col gap-5">
          <AskBox streaming={streaming} onAsk={ask.ask} onStop={ask.stop} />

          {ask.status !== "idle" && (
            <article className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900">
              <h2 className="mb-3 text-sm font-semibold text-slate-600 dark:text-slate-300">{ask.question}</h2>

              {ask.retried && streaming && (
                <p className="mb-2 text-xs text-slate-500">Re-checking citations and regenerating…</p>
              )}
              {streaming && !ask.text && <p className="text-sm text-slate-500">Searching your documents…</p>}

              {ask.status === "error" && (
                <p role="alert" className="text-sm text-red-600">
                  {ask.error?.message}
                </p>
              )}

              {abstained ? (
                <NotFoundState reason={result!.abstain_reason} />
              ) : (
                ask.text && (
                  <AnswerView
                    text={ask.text}
                    streaming={streaming}
                    activeCitation={active}
                    availableCitations={new Set(citations.map((c) => c.n))}
                    onSelectCitation={setActive}
                  />
                )
              )}

              {ask.status === "stopped" && <p className="mt-2 text-xs text-slate-500">Generation stopped.</p>}

              {result && (
                <footer className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3 dark:border-slate-800">
                  <Feedback key={result.query_id} queryId={result.query_id} />
                  <span className="text-xs text-slate-400">
                    {(result.latency_ms.total / 1000).toFixed(1)} s
                    {result.usage.input_tokens > 0 && ` · ${result.usage.input_tokens + result.usage.output_tokens} tokens`}
                  </span>
                </footer>
              )}
            </article>
          )}
        </main>

        <div>
          <CitationPanel citations={citations} active={active} answer={ask.text} onSelect={setActive} />
        </div>
      </div>
    </div>
  );
}
