import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, vi } from "vitest";
import { mockFetch, renderWithQuery } from "../test/utils";
import UploadPanel from "./UploadPanel";

const doc = { doc_id: "hr", file_name: "hr.md", title: "HR Handbook", chunks: 12, ingested_at: "2026-10-18T00:00:00Z" };

afterEach(() => vi.unstubAllGlobals());

it("lists indexed documents", async () => {
  mockFetch({ "/documents": { documents: [doc] } });
  renderWithQuery(<UploadPanel />);
  expect(await screen.findByText("HR Handbook")).toBeInTheDocument();
  expect(screen.getByText("hr.md · 12 chunks")).toBeInTheDocument();
  expect(screen.getByText("Indexed documents (1)")).toBeInTheDocument();
});

it("uploads files, polls the job and refreshes the list", async () => {
  let docs: unknown[] = [];
  const fetch = mockFetch({
    "/documents": () => ({ documents: docs }),
    "/ingest/j_1": () => {
      docs = [doc];
      return {
        job_id: "j_1",
        status: "completed",
        files: 1,
        counts: { indexed: 1, updated: 0, unchanged: 0, failed: 0, chunks: 12 },
        results: [],
        error: null,
      };
    },
    "/ingest": { job_id: "j_1", status: "queued", files: 1, counts: {}, results: [], error: null },
  });
  renderWithQuery(<UploadPanel />);
  await screen.findByText("No documents yet.");

  await userEvent.upload(screen.getByTestId("file-input"), new File(["# Hi"], "hr.md", { type: "text/markdown" }));

  expect(await screen.findByText("1 indexed · 12 chunks")).toBeInTheDocument();
  expect(await screen.findByText("HR Handbook")).toBeInTheDocument();
  const post = fetch.mock.calls.find(([, init]) => init?.method === "POST");
  expect((post![1]!.body as FormData).get("files")).toBeInstanceOf(File);
});

it("shows upload errors", async () => {
  mockFetch({
    "/documents": { documents: [] },
    "/ingest": () =>
      new Response(JSON.stringify({ error: { code: "file_too_large", message: "'big.pdf' exceeds the 25 MB limit." } }), {
        status: 413,
      }),
  });
  renderWithQuery(<UploadPanel />);
  await userEvent.upload(screen.getByTestId("file-input"), new File(["x"], "big.pdf"));
  expect(await screen.findByText("'big.pdf' exceeds the 25 MB limit.")).toBeInTheDocument();
});

it("removes the session's own upload but not shared documents", async () => {
  const shared = { ...doc, doc_id: "it", file_name: "it.md", title: "IT Policy", source_type: "preloaded" };
  let docs = [{ ...doc, source_type: "user_upload" }, shared];
  const fetch = mockFetch({
    "/documents/hr": () => {
      docs = docs.filter((d) => d.doc_id !== "hr");
      return new Response(null, { status: 204 });
    },
    "/documents": () => ({ documents: docs }),
  });
  renderWithQuery(<UploadPanel />);
  await userEvent.click(await screen.findByRole("button", { name: "Remove hr.md" }));
  await waitFor(() => expect(screen.queryByText("HR Handbook")).not.toBeInTheDocument());
  expect(screen.getByText("IT Policy")).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Remove it.md" })).not.toBeInTheDocument();
  expect(fetch.mock.calls.some(([url, init]) => String(url).endsWith("/documents/hr") && init?.method === "DELETE")).toBe(
    true,
  );
});
