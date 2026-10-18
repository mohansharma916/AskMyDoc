import { type FormEvent, useEffect, useRef, useState } from "react";

interface Props {
  streaming: boolean;
  onAsk: (question: string) => void;
  onStop: () => void;
  placeholder?: string;
}

export default function AskBox({ streaming, onAsk, onStop, placeholder }: Props) {
  const [question, setQuestion] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const q = question.trim();
    if (q && !streaming) {
      onAsk(q);
      setQuestion("");
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    }
  };

  useEffect(() => {
    textareaRef.current?.focus();
  }, []);

  return (
    <form
      onSubmit={submit}
      className="relative rounded-2xl border border-slate-300 bg-white shadow-sm transition-all focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:focus-within:border-indigo-400"
    >
      <label htmlFor="question" className="sr-only">
        Question
      </label>
      <div className="p-3.5 pb-2">
        <textarea
          ref={textareaRef}
          id="question"
          rows={2}
          value={question}
          onChange={(e) => {
            setQuestion(e.target.value);
            e.target.style.height = "auto";
            e.target.style.height = `${Math.min(e.target.scrollHeight, 140)}px`;
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={placeholder || "Ask a question about company policies, benefits, travel…"}
          className="w-full resize-none bg-transparent text-sm text-slate-900 placeholder:text-slate-400 outline-none leading-relaxed dark:text-slate-100 dark:placeholder:text-slate-500"
        />
      </div>

      <div className="flex items-center justify-between border-t border-slate-100 px-3.5 py-2.5 dark:border-slate-800">
        <div className="flex items-center gap-2 text-[11px] text-slate-500 dark:text-slate-400">
          <span className="hidden sm:inline">Press</span>
          <kbd className="rounded border border-slate-200 bg-slate-50 px-1 py-0.5 font-mono text-[10px] text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
            Enter ↵
          </kbd>
          <span className="hidden sm:inline">to send · Shift+Enter for newline</span>
        </div>

        <div className="flex items-center gap-2">
          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              aria-label="Stop"
              className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-slate-50 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
            >
              <span className="h-2 w-2 rounded-full bg-indigo-600 animate-pulse motion-reduce:animate-none"></span>
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!question.trim()}
              aria-label="Ask"
              className="flex h-8 items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 text-xs font-medium text-white transition-all hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400 dark:bg-indigo-600 dark:hover:bg-indigo-500 dark:disabled:bg-slate-800 dark:disabled:text-slate-600"
            >
              <span>Ask</span>
              <svg className="h-3 w-3 stroke-current stroke-2" fill="none" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </form>
  );
}
