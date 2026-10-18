import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, type IngestJob } from "../api/client";

const ACCEPT = ".pdf,.md,.markdown,.html,.htm,.txt";

function jobSummary(job: IngestJob): string {
  const c = job.counts;
  const parts = [
    c.indexed && `${c.indexed} indexed`,
    c.updated && `${c.updated} updated`,
    c.unchanged && `${c.unchanged} unchanged`,
    c.failed && `${c.failed} failed`,
  ].filter(Boolean);
  return `${parts.join(", ") || "Nothing to index"} · ${c.chunks} chunks`;
}

interface Props {
  onSelectDocument?: (docId: string) => void;
  activeDocId?: string | null;
}

export default function UploadPanel({ onSelectDocument, activeDocId }: Props) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);

  const documents = useQuery({ queryKey: ["documents"], queryFn: api.documents });

  const job = useQuery({
    queryKey: ["ingest", jobId],
    queryFn: () => api.ingestJob(jobId!),
    enabled: jobId !== null,
    refetchInterval: (q) => (q.state.data && ["completed", "failed"].includes(q.state.data.status) ? false : 1000),
  });

  const upload = useMutation({
    mutationFn: api.ingest,
    onSuccess: (started) => setJobId(started.job_id),
  });

  const remove = useMutation({
    mutationFn: api.deleteDocument,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      void queryClient.invalidateQueries({ queryKey: ["health"] });
    },
  });

  const jobStatus = job.data?.status;
  const jobDone = jobStatus === "completed" || jobStatus === "failed";
  useEffect(() => {
    if (jobDone) {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      void queryClient.invalidateQueries({ queryKey: ["health"] });
    }
  }, [jobDone, jobId, queryClient]);

  const send = (files: FileList | null) => {
    if (files?.length) upload.mutate(Array.from(files));
  };
  const busy = upload.isPending || (job.data !== undefined && !jobDone);
  const failedFiles = job.data?.results.filter((r) => r.status === "failed") ?? [];

  const allDocs = documents.data ?? [];
  const preloadedDocs = allDocs.filter((d) => d.source_type !== "user_upload");
  const userUploads = allDocs.filter((d) => d.source_type === "user_upload");

  return (
    <section aria-label="Documents" className="flex flex-col gap-4">
      {/* Upload Dropzone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload documents"
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && input.current?.click()}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          send(e.dataTransfer.files);
        }}
        className={`group relative cursor-pointer rounded-xl border border-dashed p-4 text-center transition-all ${
          dragging
            ? "border-indigo-500 bg-indigo-50 dark:border-indigo-400 dark:bg-indigo-950/20"
            : "border-slate-300 bg-slate-50/70 hover:border-indigo-500 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900/60 dark:hover:border-indigo-400"
        }`}
      >
        <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-full bg-white shadow-xs group-hover:scale-105 transition-transform dark:bg-slate-800">
          <svg className="h-4 w-4 text-slate-600 dark:text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 4v16m8-8H4" />
          </svg>
        </div>
        <p className="text-xs font-medium text-slate-800 dark:text-slate-200">{busy ? "Indexing…" : "Drop files or click to upload"}</p>
        <p className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">PDF, Markdown, HTML or TXT</p>
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPT}
          hidden
          data-testid="file-input"
          onChange={(e) => {
            send(e.target.files);
            e.target.value = "";
          }}
        />
      </div>

      <div aria-live="polite" className="text-xs">
        {upload.isError && <p className="text-red-600">{upload.error.message}</p>}
        {job.data?.status === "failed" && <p className="text-red-600">Ingestion failed: {job.data.error}</p>}
        {job.data?.status === "completed" && <p className="text-emerald-700 dark:text-emerald-400">{jobSummary(job.data)}</p>}
        {failedFiles.map((f) => (
          <p key={f.file_name} className="text-red-600">
            {f.file_name}: {f.error}
          </p>
        ))}
      </div>

      {/* Main Document Listing */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
            Indexed documents ({allDocs.length})
          </h2>
        </div>

        {documents.isError && <p className="text-xs text-red-600">Could not load documents.</p>}
        {allDocs.length === 0 && <p className="text-xs text-slate-500">No documents yet.</p>}

        {/* User Uploaded Section */}
        {userUploads.length > 0 && (
          <div className="mb-3">
            <div className="mb-1.5 flex items-center gap-1.5 px-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500"></span>
              User Uploads ({userUploads.length})
            </div>
            <ul className="flex flex-col gap-1">
              {userUploads.map((d) => (
                <li
                  key={d.doc_id}
                  className={`group flex items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-sm transition cursor-pointer ${
                    activeDocId === d.doc_id
                      ? "bg-indigo-50 text-indigo-950 border border-indigo-200 dark:bg-slate-800 dark:text-slate-100 dark:border-slate-700"
                      : "hover:bg-slate-100 dark:hover:bg-slate-800/60"
                  }`}
                  onClick={() => onSelectDocument?.(d.doc_id)}
                >
                  <span className="min-w-0 flex-1 truncate" title={d.file_name}>
                    <span className="font-medium text-slate-800 dark:text-slate-200">{d.title}</span>
                    <span className="block truncate text-xs text-slate-500">
                      {d.file_name} · {d.chunks} chunks
                    </span>
                  </span>
                  <div className="flex items-center gap-1">
                    <span className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400">
                      Upload
                    </span>
                    <button
                      type="button"
                      aria-label={`Remove ${d.file_name}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        remove.mutate(d.doc_id);
                      }}
                      className="rounded p-1 text-slate-400 opacity-0 hover:bg-red-50 hover:text-red-600 focus:opacity-100 group-hover:opacity-100 transition"
                    >
                      <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                      </svg>
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Pre-loaded Corpus Section */}
        {preloadedDocs.length > 0 && (
          <div>
            {userUploads.length > 0 && (
              <div className="mb-1.5 flex items-center gap-1.5 px-1 text-[11px] font-medium text-slate-500 dark:text-slate-400">
                <span className="h-1.5 w-1.5 rounded-full bg-slate-400"></span>
                Pre-loaded Corpus ({preloadedDocs.length})
              </div>
            )}
            <ul className="flex flex-col gap-1">
              {preloadedDocs.map((d) => (
                <li
                  key={d.doc_id}
                  className={`group flex items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-sm transition cursor-pointer ${
                    activeDocId === d.doc_id
                      ? "bg-indigo-50 text-indigo-950 border border-indigo-200 dark:bg-slate-800 dark:text-slate-100 dark:border-slate-700"
                      : "hover:bg-slate-100 dark:hover:bg-slate-800/60"
                  }`}
                  onClick={() => onSelectDocument?.(d.doc_id)}
                >
                  <span className="min-w-0 flex-1 truncate" title={d.file_name}>
                    <span className="font-medium text-slate-800 dark:text-slate-200">{d.title}</span>
                    <span className="block truncate text-xs text-slate-500">
                      {d.file_name} · {d.chunks} chunks
                    </span>
                  </span>
                  <div className="flex items-center gap-1">
                    <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-300">
                      Corpus
                    </span>
                    <button
                      type="button"
                      aria-label={`Remove ${d.file_name}`}
                      onClick={(e) => {
                        e.stopPropagation();
                        remove.mutate(d.doc_id);
                      }}
                      className="rounded p-1 text-slate-400 opacity-0 hover:bg-red-50 hover:text-red-600 focus:opacity-100 group-hover:opacity-100 transition"
                    >
                      <svg className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor">
                        <path d="M6.28 5.22a.75.75 0 0 0-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 1 0 1.06 1.06L10 11.06l3.72 3.72a.75.75 0 1 0 1.06-1.06L11.06 10l3.72-3.72a.75.75 0 0 0-1.06-1.06L10 8.94 6.28 5.22Z" />
                      </svg>
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  );
}
