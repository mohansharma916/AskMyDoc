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

it("loads settings and sends only changed fields", async () => {
  const fetch = mockFetch({
    "/settings": (_url: string, init?: RequestInit) =>
      init?.method === "PATCH" ? info(JSON.parse(String(init.body))) : info(),
    "/health": {},
  });
  renderWithQuery(<DeveloperSettings open onClose={() => {}} />);

  const rerankK = await screen.findByLabelText("Rerank k");
  expect(rerankK).toHaveValue(5);
  expect(screen.getByText("BAAI/bge-small-en-v1.5")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();

  await userEvent.clear(rerankK);
  await userEvent.type(rerankK, "3");
  await userEvent.selectOptions(screen.getByLabelText("Prompt version"), "answer_v2");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await screen.findByText(/Saved/);
  const patch = fetch.mock.calls.find(([, init]) => init?.method === "PATCH")!;
  expect(JSON.parse(String(patch[1]!.body))).toEqual({ rerank_k: 3, prompt_version: "answer_v2" });
  expect(screen.getAllByText("· changed")).toHaveLength(2);
});

it("shows Ollama fields only for the Ollama provider and never echoes the key", async () => {
  mockFetch({ "/settings": info() });
  renderWithQuery(<DeveloperSettings open onClose={() => {}} />);

  expect(await screen.findByLabelText("Anthropic API key")).toHaveValue("");
  expect(screen.queryByLabelText("Ollama URL")).not.toBeInTheDocument();

  await userEvent.selectOptions(screen.getByLabelText("Provider"), "ollama");
  expect(screen.getByLabelText("Ollama URL")).toBeInTheDocument();
  expect(screen.queryByLabelText(/API key/)).not.toBeInTheDocument();
  expect(screen.queryByLabelText("Effort")).not.toBeInTheDocument();
});

it("switches to Groq with its own key and a Groq model", async () => {
  const fetch = mockFetch({
    "/settings": (_url: string, init?: RequestInit) =>
      init?.method === "PATCH" ? info({ llm_provider: "groq", llm_model: "llama-3.3-70b-versatile" }) : info(),
    "/health": {},
  });
  renderWithQuery(<DeveloperSettings open onClose={() => {}} />);

  await userEvent.selectOptions(await screen.findByLabelText("Provider"), "groq");
  expect(screen.getByLabelText(/^Model/)).toHaveValue("llama-3.3-70b-versatile");
  expect(screen.getByLabelText("Temperature")).toBeInTheDocument();
  expect(screen.queryByLabelText("Base URL")).not.toBeInTheDocument();
  await userEvent.type(screen.getByLabelText("Groq API key"), "gsk-test");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));

  await screen.findByText(/Saved/);
  const patch = fetch.mock.calls.find(([, init]) => init?.method === "PATCH")!;
  expect(JSON.parse(String(patch[1]!.body))).toEqual({
    llm_provider: "groq",
    llm_model: "llama-3.3-70b-versatile",
    groq_api_key: "gsk-test",
  });
});

it("shows a base URL for OpenAI", async () => {
  mockFetch({ "/settings": info() });
  renderWithQuery(<DeveloperSettings open onClose={() => {}} />);

  await userEvent.selectOptions(await screen.findByLabelText("Provider"), "openai");
  expect(screen.getByLabelText(/^Model/)).toHaveValue("gpt-5-mini");
  expect(screen.getByLabelText("Base URL")).toHaveValue("https://api.openai.com/v1");
  expect(screen.getByLabelText("OpenAI API key")).toHaveAttribute("placeholder", "Not set");
});

it("shows server validation errors", async () => {
  mockFetch({
    "/settings": (_url: string, init?: RequestInit) =>
      init?.method === "PATCH"
        ? new Response(JSON.stringify({ error: { code: "invalid_request", message: "rerank_k must not exceed retrieve_k." } }), {
            status: 400,
          })
        : info(),
  });
  renderWithQuery(<DeveloperSettings open onClose={() => {}} />);

  const retrieveK = await screen.findByLabelText("Retrieve k");
  await userEvent.clear(retrieveK);
  await userEvent.type(retrieveK, "2");
  await userEvent.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("rerank_k must not exceed retrieve_k.");
});

it("is read-only when the server disables editing, and closes on Escape", async () => {
  const onClose = vi.fn();
  mockFetch({ "/settings": info({}, false) });
  renderWithQuery(<DeveloperSettings open onClose={onClose} />);

  expect(await screen.findByText(/Editing is disabled/)).toBeInTheDocument();
  expect(screen.getByLabelText("Rerank k")).toBeDisabled();
  await userEvent.keyboard("{Escape}");
  await waitFor(() => expect(onClose).toHaveBeenCalled());
});
