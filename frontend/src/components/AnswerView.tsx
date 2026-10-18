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
    <div className="prose-stone text-sm leading-relaxed text-stone-800 dark:text-stone-200" aria-live="polite" aria-busy={streaming}>
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed">{children}</p>,
          ul: ({ children }) => <ul className="mb-3 list-disc pl-5 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="mb-3 list-decimal pl-5 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-stone-900 dark:text-stone-100">{children}</strong>,
          code: ({ children }) => (
            <code className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-xs text-stone-800 dark:bg-stone-800 dark:text-stone-200">
              {children}
            </code>
          ),
          a: ({ href, children }) => {
            const match = href?.match(/^#cite-(\d+)$/);
            if (!match) {
              return (
                <a href={href} target="_blank" rel="noreferrer" className="text-amber-600 underline hover:text-amber-700">
                  {children}
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
                className={`mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-full px-1.5 align-[2px] text-[11px] font-semibold transition ${
                  activeCitation === n
                    ? "bg-amber-600 text-white shadow-xs"
                    : "bg-amber-100 text-amber-800 hover:bg-amber-200 dark:bg-amber-950/70 dark:text-amber-300"
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
      {streaming && <span className="ml-1 inline-block h-3.5 w-1.5 rounded-full bg-amber-600 animate-pulse align-middle" />}
    </div>
  );
}
