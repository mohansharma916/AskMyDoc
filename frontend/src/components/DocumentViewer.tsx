import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api, type ChunkDetail } from "../api/client";

interface Props {
  docId: string | null;
  onClose: () => void;
}

export default function DocumentViewer({ docId, onClose }: Props) {
  const [viewMode, setViewMode] = useState<"reader" | "chunks">("reader");
  const [searchTerm, setSearchTerm] = useState("");

  const detail = useQuery({
    queryKey: ["documentDetail", docId],
    queryFn: () => api.documentDetail(docId!),
    enabled: Boolean(docId),
  });

  const doc = detail.data;
  const isPdf = Boolean(doc?.file_name.toLowerCase().endsWith(".pdf"));
  const isPreloaded = doc?.source_type === "preloaded";

  const readingStats = useMemo(() => {
    if (!doc?.full_text) return { words: 0, minutes: 1 };
    const words = doc.full_text.trim().split(/\s+/).filter(Boolean).length;
    const minutes = Math.max(1, Math.round(words / 200));
    return { words, minutes };
  }, [doc?.full_text]);

  const filteredChunks = useMemo(() => {
    if (!doc?.chunks) return [];
    if (!searchTerm.trim()) return doc.chunks;
    const q = searchTerm.toLowerCase();
    return doc.chunks.filter(
      (c: ChunkDetail) =>
        c.text.toLowerCase().includes(q) ||
        c.section_path.some((s) => s.toLowerCase().includes(q)) ||
        (c.page !== null && String(c.page).includes(q))
    );
  }, [doc?.chunks, searchTerm]);

  if (!docId) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center text-slate-400 dark:text-slate-500">
        <svg aria-hidden className="mb-3 h-10 w-10 stroke-current stroke-1" fill="none" viewBox="0 0 24 24">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
          />
        </svg>
        <p className="text-sm font-medium">Select a document to view</p>
        <p className="mt-1 text-xs">Click any document in the sidebar to view it here</p>
      </div>
    );
  }

  if (detail.isLoading) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center text-xs text-slate-400">
        <span className="mb-2 h-5 w-5 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
        Loading document…
      </div>
    );
  }

  if (detail.isError || !doc) {
    return (
      <div className="flex h-full flex-col items-center justify-center p-6 text-center">
        <p className="text-xs text-red-600">Failed to load document.</p>
        <button
          type="button"
          onClick={() => detail.refetch()}
          className="mt-3 rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium hover:bg-slate-100 dark:border-slate-700"
        >
          Retry
        </button>
      </div>
    );
  }

  const fileUrl = doc.file_url ?? `/api/v1/documents/${encodeURIComponent(doc.doc_id)}/file`;

  return (
    <div className="flex h-full flex-col overflow-hidden bg-white dark:bg-slate-900">
      {/* Top Bar */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2.5 dark:border-slate-800">
        <div className="min-w-0 flex-1 pr-2">
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                isPdf
                  ? "bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-400"
                  : "bg-blue-50 text-blue-700 dark:bg-blue-950/60 dark:text-blue-400"
              }`}
            >
              {isPdf ? "PDF" : "Document"}
            </span>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                isPreloaded
                  ? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                  : "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400"
              }`}
            >
              {isPreloaded ? "Corpus" : "User Upload"}
            </span>
            <span className="text-xs text-slate-400">{doc.chunk_count} chunks</span>
          </div>

          <h2 className="mt-1 truncate text-sm font-semibold text-slate-900 dark:text-slate-100" title={doc.title}>
            {doc.title}
          </h2>
        </div>

        <div className="flex items-center gap-1.5">
          {/* External Open / Download for PDF */}
          {isPdf && doc.has_file && (
            <a
              href={fileUrl}
              target="_blank"
              rel="noreferrer"
              title="Open PDF in new tab"
              className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </a>
          )}

          {/* Close Panel Button */}
          <button
            type="button"
            aria-label="Close document viewer"
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
            </svg>
          </button>
        </div>
      </div>

      {/* Sub-header / View Switcher */}
      <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50/60 px-4 py-1.5 dark:border-slate-800 dark:bg-slate-900/60">
        <div className="flex items-center gap-1 rounded-lg bg-slate-200/70 p-0.5 text-xs dark:bg-slate-800">
          <button
            type="button"
            onClick={() => setViewMode("reader")}
            className={`rounded-md px-2.5 py-1 font-medium transition ${
              viewMode === "reader"
                ? "bg-white text-slate-900 shadow-xs dark:bg-slate-700 dark:text-slate-100"
                : "text-slate-600 hover:text-slate-900 dark:text-slate-400"
            }`}
          >
            {isPdf ? "PDF Viewer" : "Document Reader"}
          </button>
          <button
            type="button"
            onClick={() => setViewMode("chunks")}
            className={`rounded-md px-2.5 py-1 font-medium transition ${
              viewMode === "chunks"
                ? "bg-white text-slate-900 shadow-xs dark:bg-slate-700 dark:text-slate-100"
                : "text-slate-600 hover:text-slate-900 dark:text-slate-400"
            }`}
          >
            Chunks ({doc.chunk_count})
          </button>
        </div>

        {!isPdf && viewMode === "reader" && (
          <span className="text-[11px] text-slate-500">
            {readingStats.words} words · ~{readingStats.minutes} min read
          </span>
        )}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-hidden">
        {/* PDF Viewer */}
        {isPdf && viewMode === "reader" ? (
          doc.has_file ? (
            <div className="h-full w-full bg-slate-100 dark:bg-slate-950">
              <iframe
                src={`${fileUrl}#toolbar=1&navpanes=1`}
                title={doc.title}
                className="h-full w-full border-0"
              />
            </div>
          ) : (
            <div className="flex h-full flex-col items-center justify-center p-6 text-center text-xs text-slate-500">
              <p>Raw PDF file is not stored on server.</p>
              <button
                type="button"
                onClick={() => setViewMode("chunks")}
                className="mt-2 text-indigo-600 hover:underline"
              >
                View extracted text chunks →
              </button>
            </div>
          )
        ) : viewMode === "reader" ? (
          /* Formatted Document Viewer (Markdown / Text / HTML) */
          <div className="h-full overflow-y-auto p-5 sm:p-6">
            <div className="prose prose-slate dark:prose-invert max-w-none text-sm leading-relaxed">
              <ReactMarkdown>{doc.full_text}</ReactMarkdown>
            </div>
          </div>
        ) : (
          /* Chunks View */
          <div className="flex h-full flex-col overflow-hidden">
            <div className="border-b border-slate-200 p-2.5 dark:border-slate-800">
              <div className="relative">
                <input
                  type="text"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  placeholder="Search inside this document…"
                  className="w-full rounded-lg border border-slate-300 bg-white py-1.5 pl-8 pr-3 text-xs outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-slate-700 dark:bg-slate-800"
                />
                <svg
                  aria-hidden
                  className="absolute left-2.5 top-2 h-3.5 w-3.5 text-slate-400"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-3">
              {filteredChunks.length === 0 ? (
                <p className="py-8 text-center text-xs text-slate-400">No matching chunks found.</p>
              ) : (
                filteredChunks.map((chunk, idx) => (
                  <article
                    key={chunk.chunk_id}
                    className="rounded-lg border border-slate-200 bg-slate-50/50 p-3 text-xs dark:border-slate-800 dark:bg-slate-850"
                  >
                    <div className="mb-1.5 flex items-center justify-between text-[11px] text-slate-500">
                      <span className="font-semibold text-slate-700 dark:text-slate-300">
                        {chunk.section_path.length > 0 ? chunk.section_path.join(" › ") : "General"}
                      </span>
                      <div className="flex items-center gap-1.5">
                        {chunk.page !== null && (
                          <span className="rounded bg-slate-200 px-1 py-0.5 font-mono text-[10px] text-slate-700 dark:bg-slate-700 dark:text-slate-300">
                            p. {chunk.page}
                          </span>
                        )}
                        <span className="text-[10px] text-slate-400">#{idx + 1}</span>
                      </div>
                    </div>
                    <p className="whitespace-pre-wrap leading-relaxed text-slate-700 dark:text-slate-300">{chunk.text}</p>
                  </article>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
