import ReactMarkdown from "react-markdown";

interface Props {
  text: string;
  streaming: boolean;
  activeCitation: number | null;
  availableCitations: Set<number>;
  onSelectCitation: (n: number) => void;
}

/** Turn "[2]" markers into "#cite-2" links that the renderer shows as chips. */
export function linkCitations(text: string): string {
  return text.replace(/\[(\d+)\](?!\()/g, "[$1](#cite-$1)");
}

export default function AnswerView({ text, streaming, activeCitation, availableCitations, onSelectCitation }: Props) {
  return (
    <div className="prose-slate text-sm leading-relaxed text-slate-800 dark:text-slate-200" aria-live="polite" aria-busy={streaming}>
      <ReactMarkdown
        components={{
          h1: ({ children }) => <h1 className="mb-2 mt-4 text-base font-bold text-slate-900 dark:text-slate-100">{children}</h1>,
          h2: ({ children }) => <h2 className="mb-2 mt-3 text-sm font-bold text-slate-900 dark:text-slate-100">{children}</h2>,
          h3: ({ children }) => <h3 className="mb-1.5 mt-2.5 text-xs font-bold uppercase tracking-wide text-slate-800 dark:text-slate-200">{children}</h3>,
          p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-indigo-500 pl-3 italic text-slate-600 dark:text-slate-300">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
              <table className="min-w-full divide-y divide-slate-200 text-xs dark:divide-slate-800">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-slate-50 dark:bg-slate-800/60">{children}</thead>,
          th: ({ children }) => <th className="px-3 py-2 text-left font-semibold text-slate-800 dark:text-slate-200">{children}</th>,
          td: ({ children }) => <td className="border-t border-slate-100 px-3 py-2 text-slate-700 dark:border-slate-800 dark:text-slate-300">{children}</td>,
          hr: () => <hr className="my-4 border-slate-200 dark:border-slate-800" />,
          ul: ({ children }) => <ul className="mb-3 list-disc pl-5 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="mb-3 list-decimal pl-5 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-slate-900 dark:text-slate-100">{children}</strong>,
          code: ({ children }) => (
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800 dark:bg-slate-800 dark:text-slate-200">
              {children}
            </code>
          ),
          a: ({ href, children }) => {
            const match = href?.match(/^#cite-(\d+)$/);
            if (!match) {
              return (
                <a
                  href={href}
                  target="_blank"
                  rel="noreferrer"
                  title="Opens in new tab"
                  className="inline-flex items-center gap-0.5 text-indigo-600 underline hover:text-indigo-700 dark:text-indigo-400"
                >
                  <span>{children}</span>
                  <svg className="h-3 w-3 inline shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              );
            }
            const n = Number(match[1]);
            const available = availableCitations.has(n);
            return (
              <button
                type="button"
                aria-label={`Show source ${n}`}
                aria-pressed={activeCitation === n}
                disabled={!available}
                onClick={() => onSelectCitation(n)}
                className={`mx-0.5 inline-flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 align-[1px] text-xs font-semibold transition ${
                  activeCitation === n
                    ? "bg-indigo-600 text-white shadow-xs"
                    : "bg-indigo-100 text-indigo-700 hover:bg-indigo-200 dark:bg-indigo-950/70 dark:text-indigo-300"
                } disabled:cursor-default disabled:opacity-50`}
              >
                {n}
              </button>
            );
          },
        }}
      >
        {linkCitations(text)}
      </ReactMarkdown>
      {streaming && <span className="ml-1 inline-block h-3.5 w-1.5 rounded-full bg-indigo-600 animate-pulse motion-reduce:animate-none align-middle" />}
    </div>
  );
}
