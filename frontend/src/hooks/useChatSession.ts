import { useCallback, useEffect, useState } from "react";
import type { AskResponse, Citation } from "../api/client";

export interface ChatTurn {
  id: string;
  question: string;
  answer?: string;
  streaming?: boolean;
  abstained?: boolean;
  abstainReason?: string | null;
  citations?: Citation[];
  latencyMs?: Record<string, number>;
  usage?: { input_tokens: number; output_tokens: number; cost_usd: number | null };
  queryId?: string;
  error?: string;
  retried?: boolean;
  createdAt: number;
}

export interface ChatSession {
  id: string;
  title: string;
  createdAt: number;
  turns: ChatTurn[];
}

const STORAGE_KEY = "askdocs_browser_sessions";

function createNewSessionObj(): ChatSession {
  return {
    id: `chat_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
    title: "New chat",
    createdAt: Date.now(),
    turns: [],
  };
}

function loadInitialSessions(): ChatSession[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return parsed;
      }
    }
  } catch {
    // ignore parse error, fallback to fresh session
  }
  return [createNewSessionObj()];
}

export function useChatSession(isStreaming: boolean) {
  const [sessions, setSessions] = useState<ChatSession[]>(loadInitialSessions);
  const [activeSessionId, setActiveSessionId] = useState<string>(() => sessions[0]?.id || "");

  // Persist sessions to sessionStorage (cleared when session/browser closes)
  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch {
      // quota or private mode
    }
  }, [sessions]);

  // Keep user from accidentally reloading page by showing confirmation dialog
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      const hasContent = sessions.some((s) => s.turns.length > 0);
      if (hasContent || isStreaming) {
        e.preventDefault();
        e.returnValue = "";
        return "";
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [sessions, isStreaming]);

  const activeSession = sessions.find((s) => s.id === activeSessionId) ?? sessions[0];

  const newChat = useCallback(() => {
    const fresh = createNewSessionObj();
    setSessions((prev) => [fresh, ...prev]);
    setActiveSessionId(fresh.id);
  }, []);

  const selectChat = useCallback((id: string) => {
    setActiveSessionId(id);
  }, []);

  const deleteChat = useCallback((id: string) => {
    setSessions((prev) => {
      const filtered = prev.filter((s) => s.id !== id);
      if (filtered.length === 0) {
        const fresh = createNewSessionObj();
        return [fresh];
      }
      return filtered;
    });
    setActiveSessionId((curr) => {
      if (curr === id) {
        return sessions.find((s) => s.id !== id)?.id ?? "";
      }
      return curr;
    });
  }, [sessions]);

  const clearAllChats = useCallback(() => {
    const fresh = createNewSessionObj();
    setSessions([fresh]);
    setActiveSessionId(fresh.id);
  }, []);

  const startTurn = useCallback((question: string): string => {
    const turnId = `turn_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== activeSessionId) return s;
        const newTitle = s.title === "New chat" ? (question.length > 36 ? `${question.slice(0, 36)}…` : question) : s.title;
        const newTurn: ChatTurn = {
          id: turnId,
          question,
          answer: "",
          streaming: true,
          createdAt: Date.now(),
        };
        return {
          ...s,
          title: newTitle,
          turns: [...s.turns, newTurn],
        };
      })
    );
    return turnId;
  }, [activeSessionId]);

  const updateStreamingTurn = useCallback(
    (turnId: string, text: string, retried = false) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== activeSessionId) return s;
          return {
            ...s,
            turns: s.turns.map((t) => (t.id === turnId ? { ...t, answer: text, retried } : t)),
          };
        })
      );
    },
    [activeSessionId]
  );

  const completeTurn = useCallback(
    (turnId: string, result: AskResponse) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== activeSessionId) return s;
          return {
            ...s,
            turns: s.turns.map((t) =>
              t.id === turnId
                ? {
                    ...t,
                    answer: result.answer,
                    streaming: false,
                    abstained: result.abstained,
                    abstainReason: result.abstain_reason,
                    citations: result.citations,
                    latencyMs: result.latency_ms,
                    usage: result.usage,
                    queryId: result.query_id,
                  }
                : t
            ),
          };
        })
      );
    },
    [activeSessionId]
  );

  const failTurn = useCallback(
    (turnId: string, error: string) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== activeSessionId) return s;
          return {
            ...s,
            turns: s.turns.map((t) => (t.id === turnId ? { ...t, streaming: false, error } : t)),
          };
        })
      );
    },
    [activeSessionId]
  );

  const stopTurn = useCallback(
    (turnId: string) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== activeSessionId) return s;
          return {
            ...s,
            turns: s.turns.map((t) => (t.id === turnId ? { ...t, streaming: false } : t)),
          };
        })
      );
    },
    [activeSessionId]
  );

  return {
    sessions,
    activeSession: activeSession || sessions[0],
    activeSessionId: activeSession?.id || "",
    newChat,
    selectChat,
    deleteChat,
    clearAllChats,
    startTurn,
    updateStreamingTurn,
    completeTurn,
    failTurn,
    stopTurn,
  };
}
