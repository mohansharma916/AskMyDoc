import { useQuery } from "@tanstack/react-query";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, vi } from "vitest";
import { api } from "../api/client";
import SessionBanner from "../components/SessionBanner";
import { mockFetch, renderWithQuery } from "../test/utils";
import { SessionProvider, formatRemaining } from "./SessionProvider";

const session = (id: string, expiresIn = 300) => ({
  session_id: id,
  expires_at: "2026-10-18T00:05:00Z",
  expires_in_s: expiresIn,
  ttl_s: 300,
});

function Docs() {
  const docs = useQuery({ queryKey: ["documents"], queryFn: api.documents });
  return <p>{docs.data ? `${docs.data.length} docs` : "loading"}</p>;
}

const app = (
  <SessionProvider>
    <SessionBanner />
    <Docs />
  </SessionProvider>
);

const calls = (fetch: ReturnType<typeof mockFetch>, path: string, method = "GET") =>
  fetch.mock.calls.filter(([url, init]) => String(url).endsWith(path) && (init?.method ?? "GET") === method);

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

it("starts a session and sends its id with every request", async () => {
  const fetch = mockFetch({ "/sessions": session("s-new"), "/documents": { documents: [] } });
  renderWithQuery(app);

  expect(await screen.findByText("0 docs")).toBeInTheDocument();
  expect(calls(fetch, "/sessions", "POST")).toHaveLength(1);
  expect(localStorage.getItem("askdocs_session_id")).toBe("s-new");
  const [, init] = calls(fetch, "/documents")[0];
  expect(new Headers(init?.headers).get("X-Session-Id")).toBe("s-new");
  expect(screen.getByText(/visible only in this browser/)).toBeInTheDocument();
  expect(screen.getByLabelText("Session time left")).toHaveTextContent("5:00");
});

it("resumes this browser's session instead of starting another", async () => {
  localStorage.setItem("askdocs_session_id", "s-old");
  const fetch = mockFetch({ "/sessions/current": session("s-old", 120), "/documents": { documents: [] } });
  renderWithQuery(app);

  expect(await screen.findByText("0 docs")).toBeInTheDocument();
  expect(calls(fetch, "/sessions", "POST")).toHaveLength(0);
  expect(screen.getByLabelText("Session time left")).toHaveTextContent("2:00");
});

it("replaces a session the server already expired", async () => {
  localStorage.setItem("askdocs_session_id", "s-gone");
  mockFetch({
    "/sessions/current": new Response(JSON.stringify({ error: { code: "session_expired", message: "gone" } }), {
      status: 410,
    }),
    "/sessions": session("s-fresh"),
    "/documents": { documents: [] },
  });
  renderWithQuery(app);

  expect(await screen.findByText("0 docs")).toBeInTheDocument();
  expect(localStorage.getItem("askdocs_session_id")).toBe("s-fresh");
});

it("shows the expiry dialog at zero and starts a clean session", async () => {
  let created = 0;
  const fetch = mockFetch({
    "/sessions/current": session("s-1", 0),
    "/sessions": () => session(`s-${++created}`, created === 1 ? 1 : 300),
    "/documents": { documents: [] },
  });
  sessionStorage.setItem("askdocs_browser_sessions", "[chat history]");
  renderWithQuery(app);

  expect(await screen.findByRole("alertdialog", {}, { timeout: 3000 })).toHaveTextContent("documents, their embeddings");
  expect(calls(fetch, "/sessions/current")).toHaveLength(1); // tells the server, which deletes the data now

  await userEvent.click(screen.getByRole("button", { name: "Start a new session" }));
  await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
  expect(localStorage.getItem("askdocs_session_id")).toBe("s-2");
  expect(sessionStorage.getItem("askdocs_browser_sessions")).toBeNull();
});

it("ignores a late expired reply about a session it already replaced", async () => {
  // Regression: a stale 410 for the old session reopened the dialog right after "Start a new session".
  let created = 0;
  let release!: () => void;
  const held = new Promise<void>((resolve) => (release = resolve));
  mockFetch({
    "/sessions/current": session("s-1", 0),
    "/sessions": () => session(`s-${++created}`, created === 1 ? 1 : 300),
    "/documents": { documents: [] },
  });
  const mocked = globalThis.fetch;
  vi.stubGlobal("fetch", async (input: RequestInfo | URL, init?: RequestInit) => {
    if (!String(input).endsWith("/health")) return mocked(input, init);
    await held; // the old session's reply arrives only after the new session started
    return new Response(JSON.stringify({ error: { code: "session_expired", message: "gone" } }), { status: 410 });
  });
  renderWithQuery(app);
  await screen.findByRole("alertdialog", {}, { timeout: 3000 });
  const late = api.health().catch(() => {}); // sent with the old session id

  await userEvent.click(screen.getByRole("button", { name: "Start a new session" }));
  await waitFor(() => expect(localStorage.getItem("askdocs_session_id")).toBe("s-2"));
  release();
  await late;
  await new Promise((r) => setTimeout(r, 50));
  expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
});

it("never lets the browser cache API responses", async () => {
  const fetch = mockFetch({ "/sessions": session("s-1"), "/documents": { documents: [] } });
  renderWithQuery(app);
  await screen.findByText("0 docs");
  expect(fetch.mock.calls.every(([, init]) => init?.cache === "no-store")).toBe(true);
});

it("sends a heartbeat on user activity", async () => {
  const fetch = mockFetch({
    "/sessions/current/heartbeat": session("s-1", 300),
    "/sessions": session("s-1", 100),
    "/documents": { documents: [] },
  });
  renderWithQuery(app);
  await screen.findByText("0 docs");

  fireEvent.keyDown(window, { key: "a" });
  await waitFor(() => expect(calls(fetch, "/sessions/current/heartbeat", "POST")).toHaveLength(1));
  await waitFor(() => expect(screen.getByLabelText("Session time left")).toHaveTextContent(/^(5:00|4:59)$/));
});

it("formats the countdown", () => {
  expect(formatRemaining(300_000)).toBe("5:00");
  expect(formatRemaining(61_500)).toBe("1:02");
  expect(formatRemaining(0)).toBe("0:00");
});
