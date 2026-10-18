import { formatRemaining, useBrowserSession } from "../session/SessionProvider";

const WARN_MS = 60_000;

/** Tells the user their uploads are private to this browser and when they will be deleted. */
export default function SessionBanner() {
  const { remainingMs, ttlS, endSession } = useBrowserSession();
  const warning = remainingMs <= WARN_MS;
  const minutes = Math.round(ttlS / 60);

  return (
    <div
      role="status"
      className={`flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b px-4 py-1.5 text-xs ${
        warning
          ? "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
          : "border-slate-200 bg-slate-50 text-slate-600 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-400"
      }`}
    >
      <p className="flex items-center gap-1.5">
        <svg aria-hidden className="h-3.5 w-3.5 shrink-0" viewBox="0 0 20 20" fill="currentColor">
          <path
            fillRule="evenodd"
            d="M10 1a4.5 4.5 0 0 0-4.5 4.5V9H5a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6a2 2 0 0 0-2-2h-.5V5.5A4.5 4.5 0 0 0 10 1Zm3 8V5.5a3 3 0 1 0-6 0V9h6Z"
            clipRule="evenodd"
          />
        </svg>
        {warning ? (
          <span>
            No recent activity — your uploads and chat will be deleted in{" "}
            <strong className="font-mono tabular-nums">{formatRemaining(remainingMs)}</strong>. Move the mouse or press a
            key to stay.
          </span>
        ) : (
          <span>
            Private session: documents you upload are visible only in this browser and are deleted after {minutes}{" "}
            minutes without activity.
          </span>
        )}
      </p>
      <span className="flex items-center gap-3">
        {!warning && (
          <span>
            Time left:{" "}
            <strong className="font-mono tabular-nums" aria-label="Session time left">
              {formatRemaining(remainingMs)}
            </strong>
          </span>
        )}
        <button
          type="button"
          onClick={endSession}
          className="font-semibold underline-offset-2 hover:text-red-600 hover:underline"
        >
          End session now
        </button>
      </span>
    </div>
  );
}
