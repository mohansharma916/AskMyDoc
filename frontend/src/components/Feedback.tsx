import { useMutation } from "@tanstack/react-query";
import { api, type Rating } from "../api/client";

export default function Feedback({ queryId }: { queryId: string }) {
  const send = useMutation({ mutationFn: (rating: Rating) => api.feedback(queryId, rating) });

  if (send.isSuccess) {
    return <p className="text-xs text-slate-500">Thanks for the feedback.</p>;
  }

  const button = "rounded-md border border-slate-300 px-2.5 py-1 text-xs hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800";
  return (
    <div className="flex items-center gap-2 text-xs text-slate-500">
      <span>Was this helpful?</span>
      <button type="button" className={button} disabled={send.isPending} onClick={() => send.mutate("helpful")}>
        👍 Helpful
      </button>
      <button type="button" className={button} disabled={send.isPending} onClick={() => send.mutate("not_helpful")}>
        👎 Not helpful
      </button>
      {send.isError && <span className="text-red-600">{send.error.message}</span>}
    </div>
  );
}
