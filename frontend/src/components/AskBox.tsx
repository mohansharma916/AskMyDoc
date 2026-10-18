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
    }
  };

  useEffect(() => {
    if (!streaming && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [streaming]);

  return (
    <form
      onSubmit={submit}
      className="relative rounded-2xl border border-stone-300/80 bg-white shadow-sm transition-all focus-within:border-amber-600 focus-within:ring-2 focus-within:ring-amber-600/20 dark:border-stone-700 dark:bg-stone-900 dark:focus-within:border-amber-500"
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
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder={placeholder || "Ask a question about company policies, benefits, travel…"}
          className="w-full resize-none bg-transparent text-sm text-stone-900 placeholder:text-stone-400 outline-none leading-relaxed dark:text-stone-100 dark:placeholder:text-stone-500"
        />
      </div>

      <div className="flex items-center justify-between border-t border-stone-100/80 px-3.5 py-2.5 dark:border-stone-800/80">
        <div className="flex items-center gap-2 text-[11px] text-stone-400 dark:text-stone-500">
          <span className="hidden sm:inline">Press</span>
          <kbd className="rounded border border-stone-200 bg-stone-50 px-1 py-0.5 font-mono text-[10px] text-stone-500 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-400">
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
              className="flex items-center gap-1.5 rounded-xl border border-stone-300 bg-stone-50 px-3 py-1.5 text-xs font-medium text-stone-700 hover:bg-stone-100 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300 dark:hover:bg-stone-750"
            >
              <span className="h-2 w-2 rounded-full bg-amber-600 animate-pulse"></span>
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!question.trim()}
              aria-label="Ask"
              className="flex h-8 items-center gap-1.5 rounded-xl bg-stone-900 px-3.5 text-xs font-medium text-white transition-all hover:bg-stone-800 disabled:cursor-not-allowed disabled:bg-stone-200 disabled:text-stone-400 dark:bg-amber-600 dark:hover:bg-amber-500 dark:disabled:bg-stone-800 dark:disabled:text-stone-600"
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
