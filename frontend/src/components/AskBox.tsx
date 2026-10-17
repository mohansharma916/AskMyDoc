import { type FormEvent, useState } from "react";

interface Props {
  streaming: boolean;
  onAsk: (question: string) => void;
  onStop: () => void;
}

export default function AskBox({ streaming, onAsk, onStop }: Props) {
  const [question, setQuestion] = useState("");

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const q = question.trim();
    if (q && !streaming) onAsk(q);
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <label htmlFor="question" className="sr-only">
        Question
      </label>
      <textarea
        id="question"
        rows={3}
        value={question}
        onChange={(e) => setQuestion(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            submit();
          }
        }}
        placeholder="Ask a question about your documents…"
        className="w-full resize-y rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/30 dark:border-slate-700 dark:bg-slate-900"
      />
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs text-slate-500">Enter to ask · Shift+Enter for a new line</span>
        {streaming ? (
          <button
            type="button"
            onClick={onStop}
            className="rounded-lg border border-slate-300 px-4 py-1.5 text-sm font-medium hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            Stop
          </button>
        ) : (
          <button
            type="submit"
            disabled={!question.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Ask
          </button>
        )}
      </div>
    </form>
  );
}
