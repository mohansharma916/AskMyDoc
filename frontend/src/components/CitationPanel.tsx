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
      <mark key={i} className="rounded bg-amber-200/80 px-0.5 text-inherit dark:bg-amber-500/30">
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
        <h2 className="text-[11px] font-semibold uppercase tracking-wider text-stone-500 dark:text-stone-400">
          Sources ({citations.length})
        </h2>
      </div>
      <ol className="flex flex-col gap-2">
        {citations.map((c) => {
          const selected = c.n === active;
          return (
            <li key={c.n}>
              <button
                type="button"
                onClick={() => onSelect(c.n)}
                aria-current={selected}
                className={`w-full rounded-xl border p-3 text-left transition-all ${
                  selected
                    ? "border-amber-600 bg-amber-50/60 shadow-xs dark:border-amber-500/70 dark:bg-amber-950/20"
                    : "border-stone-200 bg-white hover:border-stone-300 dark:border-stone-800 dark:bg-stone-900"
                }`}
              >
                <div className="flex items-baseline gap-2">
                  <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-600 px-1.5 text-[11px] font-semibold text-white">
                    {c.n}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-xs font-semibold text-stone-800 dark:text-stone-200" title={c.file_name}>
                    {c.file_name}
                  </span>
                  {c.page !== null && <span className="shrink-0 font-mono text-[11px] text-stone-400">p. {c.page}</span>}
                </div>
                {c.section_path.length > 0 && (
                  <p className="mt-1 truncate text-xs text-stone-500 dark:text-stone-400">{c.section_path.join(" › ")}</p>
                )}
                <p
                  className={`mt-2 whitespace-pre-line text-xs leading-relaxed text-stone-700 dark:text-stone-300 ${
                    selected ? "" : "line-clamp-3"
                  }`}
                >
                  {selected ? highlight(c.snippet, sentencesCiting(answer, c.n)) : c.snippet}
                </p>
                {onViewDoc && (
                  <div className="mt-2.5 pt-2 border-t border-stone-100 flex justify-end dark:border-stone-800">
                    <span
                      onClick={(e) => {
                        e.stopPropagation();
                        onViewDoc(c.doc_id);
                      }}
                      className="text-[11px] font-medium text-amber-600 hover:text-amber-700 hover:underline dark:text-amber-500"
                    >
                      Inspect full document →
                    </span>
                  </div>
                )}
              </button>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
