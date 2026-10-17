import { useCallback, useRef, useState } from "react";
import { type AskResponse, ApiError, streamAsk } from "../api/client";

export type AskStatus = "idle" | "streaming" | "done" | "stopped" | "error";

export interface AskState {
  question: string;
  text: string;
  status: AskStatus;
  result: AskResponse | null;
  error: ApiError | null;
  queryId: string | null;
  retried: boolean;
}

const INITIAL: AskState = {
  question: "",
  text: "",
  status: "idle",
  result: null,
  error: null,
  queryId: null,
  retried: false,
};

export function useAskStream() {
  const [state, setState] = useState<AskState>(INITIAL);
  const controller = useRef<AbortController | null>(null);

  const ask = useCallback(async (question: string) => {
    controller.current?.abort();
    const abort = new AbortController();
    controller.current = abort;
    setState({ ...INITIAL, question, status: "streaming" });
    try {
      for await (const event of streamAsk(question, abort.signal)) {
        if (event.type === "meta") setState((s) => ({ ...s, queryId: event.query_id }));
        else if (event.type === "token") setState((s) => ({ ...s, text: s.text + event.text }));
        else if (event.type === "retry") setState((s) => ({ ...s, text: "", retried: true }));
        else if (event.type === "done")
          setState((s) => ({ ...s, status: "done", result: event.result, text: event.result.answer }));
      }
    } catch (err) {
      if (abort.signal.aborted) {
        setState((s) => ({ ...s, status: "stopped" }));
      } else {
        const error = err instanceof ApiError ? err : new ApiError(0, "network_error", "Could not reach the server.");
        setState((s) => ({ ...s, status: "error", error }));
      }
    }
  }, []);

  const stop = useCallback(() => controller.current?.abort(), []);

  return { ...state, ask, stop };
}
