import { useQueryClient } from "@tanstack/react-query";
import { type ReactNode, createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api, browserSession, type SessionInfo } from "../api/client";

const ACTIVITY_EVENTS = ["pointerdown", "pointermove", "keydown", "wheel", "touchstart", "scroll"] as const;
const HEARTBEAT_EVERY_MS = 10_000; // at most one heartbeat per 10 s of activity

interface SessionContextValue {
  /** Milliseconds until this browser's uploads are deleted, unless there is activity. */
  remainingMs: number;
  ttlS: number;
  endSession: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function useBrowserSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useBrowserSession must be used inside <SessionProvider>");
  return value;
}

type Status = "starting" | "active" | "expired" | "error";

/** Gives the app a private, expiring server session and remounts it whenever a new one starts. */
export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<Status>("starting");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [ttlS, setTtlS] = useState(300);
  const [expiresAt, setExpiresAt] = useState(0); // local clock, from the server's expires_in_s
  const [now, setNow] = useState(() => Date.now());
  const lastBeat = useRef(0);
  const beating = useRef(false);
  const resumed = useRef(false);

  const adopt = useCallback((info: SessionInfo) => {
    browserSession.set(info.session_id);
    setSessionId(info.session_id);
    setTtlS(info.ttl_s);
    setExpiresAt(Date.now() + info.expires_in_s * 1000);
    setNow(Date.now());
    setStatus("active");
  }, []);

  const startFresh = useCallback(async () => {
    setStatus("starting");
    browserSession.clear();
    queryClient.clear();
    try {
      sessionStorage.clear(); // chat history and other per-session UI state
    } catch {}
    try {
      adopt(await api.createSession());
    } catch {
      setStatus("error");
    }
  }, [adopt, queryClient]);

  // Resume this browser's session, or start one (once, even under StrictMode's double effects).
  useEffect(() => {
    if (resumed.current) return;
    resumed.current = true;
    (async () => {
      if (browserSession.id()) {
        try {
          adopt(await api.currentSession());
          return;
        } catch {
          // expired or unknown: start a new session
        }
      }
      await startFresh();
    })();
  }, [adopt, startFresh]);

  // Any request that finds the session expired ends it in the UI too.
  useEffect(() => browserSession.onExpired(() => setStatus("expired")), []);

  // Real user activity (not background polling) keeps the session alive.
  useEffect(() => {
    if (status !== "active") return;
    const onActivity = () => {
      if (beating.current || Date.now() - lastBeat.current < HEARTBEAT_EVERY_MS) return;
      beating.current = true;
      lastBeat.current = Date.now();
      api
        .heartbeat()
        .then((info) => setExpiresAt(Date.now() + info.expires_in_s * 1000))
        .catch(() => {})
        .finally(() => {
          beating.current = false;
        });
    };
    ACTIVITY_EVENTS.forEach((e) => window.addEventListener(e, onActivity, { passive: true, capture: true }));
    return () => ACTIVITY_EVENTS.forEach((e) => window.removeEventListener(e, onActivity, { capture: true }));
  }, [status]);

  // Countdown; at zero, ask the server, which deletes the expired session's data right away.
  useEffect(() => {
    if (status !== "active") return;
    const timer = window.setInterval(() => {
      const t = Date.now();
      setNow(t);
      if (t >= expiresAt) {
        setStatus("expired");
        api.currentSession().catch(() => {});
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [status, expiresAt]);

  const endSession = useCallback(() => {
    api
      .endSession()
      .catch(() => {})
      .finally(() => void startFresh());
  }, [startFresh]);

  if (status === "starting" || (status === "error" && !sessionId)) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50 text-sm text-slate-500 dark:bg-slate-950">
        {status === "error" ? (
          <p role="alert">
            Could not start a session. Is the API running?{" "}
            <button type="button" className="font-semibold text-indigo-600 underline" onClick={() => void startFresh()}>
              Try again
            </button>
          </p>
        ) : (
          <p>Starting your private session…</p>
        )}
      </div>
    );
  }

  return (
    <SessionContext.Provider value={{ remainingMs: Math.max(0, expiresAt - now), ttlS, endSession }}>
      <div key={sessionId} className="contents">
        {children}
      </div>
      {status === "expired" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">
          <div
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="session-expired-title"
            className="w-full max-w-sm rounded-2xl bg-white p-6 text-center shadow-xl dark:bg-slate-900"
          >
            <h2 id="session-expired-title" className="text-lg font-semibold">
              Session expired
            </h2>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">
              There was no activity for {Math.round(ttlS / 60)} minutes, so your uploaded documents, their embeddings and
              this chat history were deleted.
            </p>
            <button
              type="button"
              autoFocus
              onClick={() => void startFresh()}
              className="mt-5 w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              Start a new session
            </button>
          </div>
        </div>
      )}
    </SessionContext.Provider>
  );
}

export function formatRemaining(ms: number): string {
  const total = Math.ceil(ms / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}
