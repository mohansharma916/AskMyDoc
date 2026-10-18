import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type ChunkDetail } from "../api/client";

interface Props {
  docId: string | null;
  onClose: () => void;
}

export default function DocumentPreview({ docId, onClose }: Props) {
  const [searchTerm, setSearchTerm] = useState("");

  const detail = useQuery({
    queryKey: ["documentDetail", docId],
    queryFn: () => api.documentDetail(docId!),
    enabled: Boolean(docId),
  });

  if (!docId) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center text-stone-400 dark:text-stone-500">
        <svg aria-hidden className="mb-3 h-10 w-10 stroke-current stroke-1" fill="none" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z" />
        </svg>
        <p className="text-sm font-medium">Select a document to inspect</p>
        <p className="mt-1 text-xs">Click any pre-loaded or uploaded document in the sidebar</p>
      </div>
    );
  }

  const doc = detail.data;
  const isPreloaded = doc?.source_type === "preloaded";

  const filteredChunks = doc?.chunks.filter((c: ChunkDetail) => {
    if (!searchTerm.trim()) return true;
    const term = searchTerm.toLowerCase();
    return (
      c.text.toLowerCase().includes(term) ||
      c.section_path.some((s) => s.toLowerCase().includes(term)) ||
      (c.page && String(c.page).includes(term))
    );
  }) ?? [];

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-stone-200 bg-white shadow-sm dark:border-stone-800 dark:bg-stone-900">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-stone-100 p-4 dark:border-stone-800">
        <div className="min-w-0 flex-1 pr-2">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                isPreloaded
                  ? "bg-stone-100 text-stone-700 dark:bg-stone-800 dark:text-stone-300"
                  : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400"
              }`}
            >
              {isPreloaded ? "📚 Pre-loaded Corpus" : "📤 User Upload"}
            </span>
            {doc && (
              <span className="text-xs text-stone-400 dark:text-stone-500">
                {doc.chunk_count} {doc.chunk_count === 1 ? "chunk" : "chunks"}
              </span>
            )}
          </div>
          <h2 className="mt-1.5 truncate text-base font-serif font-semibold text-stone-900 dark:text-stone-100" title={doc?.title || docId}>
            {doc?.title || docId}
          </h2>
          <p className="truncate text-xs text-stone-500 dark:text-stone-400" title={doc?.file_name}>
            {doc?.file_name || docId}
          </p>
        </div>
        <button
          type="button"
          aria-label="Close document preview"
          onClick={onClose}
          className="rounded-lg p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-600 dark:hover:bg-stone-800 dark:hover:text-stone-300"
        >
          <svg aria-hidden className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
          </svg>
        </button>
      </div>

      {/* Search within document */}
      {doc && doc.chunks.length > 0 && (
        <div className="border-b border-stone-100 px-4 py-2.5 dark:border-stone-800">
          <div className="relative">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filter chunks in this document…"
              className="w-full rounded-lg border border-stone-200 bg-stone-50/50 py-1.5 pl-8 pr-3 text-xs outline-none transition focus:border-amber-600 focus:bg-white focus:ring-1 focus:ring-amber-600/30 dark:border-stone-700 dark:bg-stone-800 dark:focus:border-amber-500"
            />
            <svg
              aria-hidden
              className="absolute left-2.5 top-2 h-3.5 w-3.5 text-stone-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            {searchTerm && (
              <button
                type="button"
                onClick={() => setSearchTerm("")}
                className="absolute right-2.5 top-2 text-xs text-stone-400 hover:text-stone-600"
              >
                ×
              </button>
            )}
          </div>
        </div>
      )}

      {/* Content / Chunks view */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {detail.isLoading && (
          <div className="py-8 text-center text-xs text-stone-400">Loading document content…</div>
        )}

        {detail.isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-600 dark:border-red-900/50 dark:bg-red-950/30">
            Could not load document preview.
          </div>
        )}

        {doc && filteredChunks.length === 0 && (
          <p className="py-8 text-center text-xs text-stone-400">
            {searchTerm ? "No matching chunks found." : "No chunks available."}
          </p>
        )}

        {filteredChunks.map((chunk, idx) => (
          <article
            key={chunk.chunk_id}
            className="rounded-lg border border-stone-200/80 bg-stone-50/40 p-3 transition hover:border-stone-300 dark:border-stone-800 dark:bg-stone-900/40"
          >
            <div className="mb-2 flex flex-wrap items-center justify-between gap-1 text-[11px] text-stone-500 dark:text-stone-400">
              <span className="font-medium text-stone-700 dark:text-stone-300">
                {chunk.section_path.length > 0 ? chunk.section_path.join(" › ") : "General"}
              </span>
              <div className="flex items-center gap-2">
                {chunk.page !== null && (
                  <span className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-[10px] text-stone-600 dark:bg-stone-800 dark:text-stone-400">
                    p. {chunk.page}
                  </span>
                )}
                <span className="text-[10px] text-stone-400">#{idx + 1}</span>
              </div>
            </div>
            <p className="whitespace-pre-wrap text-xs leading-relaxed text-stone-700 dark:text-stone-300">
              {chunk.text}
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
