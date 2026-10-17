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

export default function UploadPanel() {
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
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
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

  return (
    <section aria-label="Documents" className="flex flex-col gap-4">
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
        className={`cursor-pointer rounded-lg border-2 border-dashed px-4 py-6 text-center text-sm transition ${
          dragging
            ? "border-indigo-500 bg-indigo-50 dark:bg-indigo-950/40"
            : "border-slate-300 hover:border-indigo-400 dark:border-slate-700"
        }`}
      >
        <p className="font-medium">{busy ? "Indexing…" : "Drop files or click to upload"}</p>
        <p className="mt-1 text-xs text-slate-500">PDF, Markdown, HTML or TXT</p>
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

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Indexed documents ({documents.data?.length ?? 0})
        </h2>
        {documents.isError && <p className="text-xs text-red-600">Could not load documents.</p>}
        {documents.data?.length === 0 && <p className="text-xs text-slate-500">No documents yet.</p>}
        <ul className="flex flex-col gap-1">
          {documents.data?.map((d) => (
            <li
              key={d.doc_id}
              className="group flex items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-slate-100 dark:hover:bg-slate-800"
            >
              <span className="min-w-0 flex-1 truncate" title={d.file_name}>
                {d.title}
                <span className="block truncate text-xs text-slate-500">
                  {d.file_name} · {d.chunks} chunks
                </span>
              </span>
              <button
                type="button"
                aria-label={`Remove ${d.file_name}`}
                onClick={() => remove.mutate(d.doc_id)}
                className="rounded px-1.5 text-slate-400 opacity-0 hover:bg-red-50 hover:text-red-600 focus:opacity-100 group-hover:opacity-100"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
