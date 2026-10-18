import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, vi } from "vitest";
import type { RuntimeSettings, SettingsInfo } from "../api/client";
import { mockFetch, renderWithQuery } from "../test/utils";
import DeveloperSettings from "./DeveloperSettings";

const settings: RuntimeSettings = {
  llm_provider: "anthropic",
  llm_model: "claude-opus-5-5",
  api_keys_set: { anthropic: true, openai: false, groq: false },
  llm_effort: "low",
  llm_temperature: 0.1,
  llm_timeout_s: 30,
  ollama_url: "http://localhost:11434",
  openai_base_url: "https://api.openai.com/v1",
  rerank_model: "BAAI/bge-reranker-base",
  prompt_version: "answer_v1",
  chunk_size: 512,
  chunk_overlap: 64,
  retrieve_k: 20,
  rerank_k: 5,
  abstain_threshold: 0.03,
  max_upload_mb: 25,
};

const info = (overrides: Partial<RuntimeSettings> = {}, editable = true): SettingsInfo => ({
  editable,
  settings: { ...settings, ...overrides },
  defaults: settings,
  restart_required: { embed_model: "BAAI/bge-small-en-v1.5" },
  prompt_versions: ["answer_v1", "answer_v2"],
});

afterEach(() => vi.unstubAllGlobals());

it("shows only provider, model and API key", async () => {
  mockFetch({ "/settings": info() });
  renderWithQuery(<DeveloperSettings open onClose={() => {}} />);

  expect(await screen.findByLabelText("Provider")).toHaveValue("anthropic");
  expect(screen.getByLabelText("Model")).toHaveValue("claude-opus-5-5");
  expect(screen.getByLabelText("API key")).toHaveValue("");
  expect(document.querySelectorAll("input, select")).toHaveLength(3);
  expect(screen.queryByText(/Restart required/)).not.toBeInTheDocument();
  expect(screen.queryByText("BAAI/bge-small-en-v1.5")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
});

it("switches to Groq with its own key and a Groq model", async () => {
  const fetch = mockFetch({
    "/settings": (_url: string, init?: RequestInit) =>
      init?.method === "PATCH" ? info({ llm_provider: "groq", llm_model: "llama-3.3-70b-versatile" }) : info(),
    "/health": {},
  });
  renderWithQuery(<DeveloperSettings open onClose={() => {}} />);

  await userEvent.selectOptions(await screen.findByLabelText("Provider"), "groq");
  expect(screen.getByLabelText("Model")).toHaveValue("llama-3.3-70b-versatile");
  expect(screen.getByLabelText("API key")).toHaveAttribute("placeholder", "Not set");
  await userEvent.type(screen.getByLabelText("API key"), "gsk-test");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await screen.findByText(/Saved/);
  const patch = fetch.mock.calls.find(([, init]) => init?.method === "PATCH")!;
  expect(JSON.parse(String(patch[1]!.body))).toEqual({
    llm_provider: "groq",
    llm_model: "llama-3.3-70b-versatile",
    groq_api_key: "gsk-test",
  });
});

it("hides the API key for Ollama", async () => {
  mockFetch({ "/settings": info() });
  renderWithQuery(<DeveloperSettings open onClose={() => {}} />);

  await userEvent.selectOptions(await screen.findByLabelText("Provider"), "ollama");
  expect(screen.getByLabelText("Model")).toHaveValue("llama3.1");
  expect(screen.queryByLabelText("API key")).not.toBeInTheDocument();
});

it("shows server errors", async () => {
  mockFetch({
    "/settings": (_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? new Response(JSON.stringify({ error: { code: "invalid_request", message: "llm_model: too long" } }), { status: 400 })
        : info(),
  });
  renderWithQuery(<DeveloperSettings open onClose={() => {}} />);

  const model = await screen.findByLabelText("Model");
  await userEvent.type(model, "-x");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("llm_model: too long");
});

it("is read-only when the server disables editing, and closes on Escape", async () => {
  const onClose = vi.fn();
  mockFetch({ "/settings": info({}, false) });
  renderWithQuery(<DeveloperSettings open onClose={onClose} />);

  expect(await screen.findByText(/Editing is disabled/)).toBeInTheDocument();
  expect(screen.getByLabelText("Model")).toBeDisabled();
  await userEvent.keyboard("{Escape}");
  await waitFor(() => expect(onClose).toHaveBeenCalled());
});
