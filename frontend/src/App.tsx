import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "./api/client";
import AnswerView from "./components/AnswerView";
import AskBox from "./components/AskBox";
import CitationPanel from "./components/CitationPanel";
import Feedback from "./components/Feedback";
import NotFoundState from "./components/NotFoundState";
import UploadPanel from "./components/UploadPanel";
import { useAskStream } from "./hooks/useAskStream";

export default function App() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
  const ask = useAskStream();
  const [active, setActive] = useState<number | null>(null);

  const result = ask.result;
  const citations = result?.citations ?? [];
  useEffect(() => setActive(result?.citations[0]?.n ?? null), [result]);

  const streaming = ask.status === "streaming";
  const abstained = result?.abstained ?? false;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3 dark:border-slate-800 dark:bg-slate-900">
        <h1 className="text-lg font-semibold">Ask My Docs</h1>
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
      </header>

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
