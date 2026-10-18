import type { ReactNode } from "react";
import type { Citation } from "../api/client";

const STOPWORDS = new Set(
  "the and for with that this from are was were has have had not but you your their there which what when where who why how can will per each".split(
    " ",
  ),
);

/** The answer sentences that cite excerpt n. */
export function sentencesCiting(answer: string, n: number): string[] {
  return answer.split(/(?<=[.!?](?:\s*\[\d+\])*)\s+/).filter((s) => s.includes(`[${n}]`));
}

/** Wrap words shared with the citing sentences in <mark> so the supporting text stands out. */
export function highlight(snippet: string, sentences: string[]): ReactNode[] {
  const terms = new Set(
    sentences
      .join(" ")
      .replace(/\[\d+\]/g, "")
      .toLowerCase()
      .match(/[\p{L}\p{N}][\p{L}\p{N}.,%-]*[\p{L}\p{N}%]|\p{N}/gu)
      ?.filter((w) => (w.length >= 4 || /\d/.test(w)) && !STOPWORDS.has(w)),
  );
  if (!terms.size) return [snippet];
  return snippet.split(/([\p{L}\p{N}][\p{L}\p{N}.,%-]*[\p{L}\p{N}%]|\p{N})/u).map((part, i) =>
    terms.has(part.toLowerCase()) ? (
      <mark key={i} className="rounded bg-amber-200/80 px-0.5 text-inherit dark:bg-amber-400/25 dark:text-amber-200">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

interface Props {
  citations: Citation[];
  active: number | null;
  answer: string;
  onSelect: (n: number) => void;
  onViewDoc?: (docId: string) => void;
}

export default function CitationPanel({ citations, active, answer, onSelect, onViewDoc }: Props) {
  if (!citations.length) return null;
  return (
    <aside aria-label="Sources" className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
          Sources ({citations.length})
        </h2>
      </div>
      <ol className="flex flex-col gap-2">
        {citations.map((c) => {
          const selected = c.n === active;
          return (
            <li key={c.n}>
              <article
                aria-current={selected}
                className={`w-full rounded-xl border p-3 transition-all ${
                  selected
                    ? "border-indigo-500 bg-indigo-50/70 shadow-xs dark:border-indigo-500/70 dark:bg-indigo-950/20"
                    : "border-slate-200 bg-white hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900"
                }`}
              >
                <button
                  type="button"
                  onClick={() => onSelect(c.n)}
                  className="w-full text-left focus:outline-none"
                  aria-label={`Select citation ${c.n} from ${c.file_name}`}
                >
                  <div className="flex items-baseline gap-2">
                    <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-indigo-600 px-1.5 text-[11px] font-semibold text-white">
                      {c.n}
                    </span>
                    <span className="min-w-0 flex-1 truncate text-xs font-semibold text-slate-800 dark:text-slate-200" title={c.file_name}>
                      {c.file_name}
                    </span>
                    {c.page !== null && <span className="shrink-0 font-mono text-[11px] text-slate-400">p. {c.page}</span>}
                  </div>
                  {c.section_path.length > 0 && (
                    <p className="mt-1 truncate text-xs text-slate-500 dark:text-slate-400">{c.section_path.join(" › ")}</p>
                  )}
                  <p
                    className={`mt-2 whitespace-pre-line text-xs leading-relaxed text-slate-700 dark:text-slate-300 ${
                      selected ? "" : "line-clamp-3"
                    }`}
                  >
                    {selected ? highlight(c.snippet, sentencesCiting(answer, c.n)) : c.snippet}
                  </p>
                </button>
                {onViewDoc && (
                  <div className="mt-2.5 pt-2 border-t border-slate-100 flex justify-end dark:border-slate-800">
                    <button
                      type="button"
                      onClick={() => onViewDoc(c.doc_id)}
                      className="text-[11px] font-medium text-indigo-600 hover:text-indigo-700 hover:underline dark:text-indigo-400"
                    >
                      Open in viewer →
                    </button>
                  </div>
                )}
              </article>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
