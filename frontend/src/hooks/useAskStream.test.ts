import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { useAskStream } from "./useAskStream";

const done = {
  query_id: "q_1",
  question: "q",
  answer: "Twenty weeks [1].",
  abstained: false,
  abstain_reason: null,
  citations: [],
  usage: { input_tokens: 1, output_tokens: 1, cost_usd: 0 },
  latency_ms: { total: 10 },
  model: "m",
  prompt_version: "answer_v1",
};

function sseResponse(events: [string, unknown][]) {
  const encoder = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      // One chunk per event, split mid-message, to exercise the incremental parser.
      for (const [e, d] of events) {
        const message = `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`;
        controller.enqueue(encoder.encode(message.slice(0, 7)));
        controller.enqueue(encoder.encode(message.slice(7)));
      }
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

afterEach(() => vi.unstubAllGlobals());

it("streams tokens, resets on retry and finishes with the result", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      sseResponse([
        ["meta", { query_id: "q_1" }],
        ["token", { text: "No cites." }],
        ["retry", { reason: "citation_check_failed" }],
        ["token", { text: "Twenty " }],
        ["token", { text: "weeks [1]." }],
        ["done", done],
      ]),
    ),
  );
  const { result } = renderHook(() => useAskStream());
  await act(() => result.current.ask("q"));
  expect(result.current.status).toBe("done");
  expect(result.current.text).toBe("Twenty weeks [1].");
  expect(result.current.retried).toBe(true);
  expect(result.current.queryId).toBe("q_1");
});

it("surfaces API and stream errors", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => new Response(JSON.stringify({ error: { code: "invalid_request", message: "bad" } }), { status: 400 })),
  );
  const { result } = renderHook(() => useAskStream());
  await act(() => result.current.ask("q"));
  expect(result.current.status).toBe("error");
  expect(result.current.error?.code).toBe("invalid_request");

  vi.stubGlobal("fetch", vi.fn(async () => sseResponse([["error", { code: "timeout", message: "slow", status: 504 }]])));
  await act(() => result.current.ask("q"));
  expect(result.current.error?.status).toBe(504);

  vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
  await act(() => result.current.ask("q"));
  expect(result.current.error?.code).toBe("network_error");
});

it("stops generation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      (_url: string, init: RequestInit) =>
        new Promise((_, reject) => init.signal?.addEventListener("abort", () => reject(new DOMException("x", "AbortError")))),
    ),
  );
  const { result } = renderHook(() => useAskStream());
  let pending: Promise<void>;
  act(() => {
    pending = result.current.ask("q");
  });
  expect(result.current.status).toBe("streaming");
  act(() => result.current.stop());
  await act(() => pending);
  await waitFor(() => expect(result.current.status).toBe("stopped"));
});
