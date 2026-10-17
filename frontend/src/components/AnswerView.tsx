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
    <div className="prose-sm max-w-none text-[15px] leading-relaxed" aria-live="polite" aria-busy={streaming}>
      <ReactMarkdown
        components={{
          p: ({ children }) => <p className="mb-3 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="mb-3 list-disc pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="mb-3 list-decimal pl-5">{children}</ol>,
          a: ({ href, children }) => {
            const match = href?.match(/^#cite-(\d+)$/);
            if (!match) {
              return (
                <a href={href} target="_blank" rel="noreferrer" className="text-indigo-600 underline">
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
                    ? "bg-indigo-600 text-white"
                    : "bg-indigo-100 text-indigo-700 hover:bg-indigo-200 dark:bg-indigo-950 dark:text-indigo-300"
                } disabled:cursor-default disabled:opacity-60`}
              >
                {n}
              </button>
            );
          },
        }}
      >
        {linkCitations(text)}
      </ReactMarkdown>
      {streaming && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-slate-400 align-middle" />}
    </div>
  );
}
