import { expect, type Page, test } from "@playwright/test";

const documents = [
  { doc_id: "employee-handbook", file_name: "employee_handbook.md", title: "Employee Handbook", chunks: 14, ingested_at: "2026-10-18T00:00:00Z" },
];

const result = {
  query_id: "q_e2e",
  question: "How long is parental leave for primary caregivers?",
  answer: "Primary caregivers receive 20 weeks of fully paid parental leave [1].",
  abstained: false,
  abstain_reason: null,
  citations: [
    {
      n: 1,
      chunk_id: "c1",
      doc_id: "employee-handbook",
      file_name: "employee_handbook.md",
      page: null,
      section_path: ["Northwind Robotics Employee Handbook", "Time Off", "Parental leave"],
      snippet: "Primary caregivers receive 20 weeks of fully paid parental leave.",
    },
  ],
  usage: { input_tokens: 2100, output_tokens: 40, cost_usd: 0.009 },
  latency_ms: { retrieve: 50, rerank: 1100, generate: 1300, total: 2450 },
  model: "claude-opus-5-5",
  prompt_version: "answer_v1",
};

function sse(events: [string, unknown][]): string {
  return events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join("");
}

async function mockApi(page: Page, streamBody: string) {
  const feedback: unknown[] = [];
  await page.route("**/api/v1/health", (r) =>
    r.fulfill({ json: { status: "ok", database: true, qdrant: true, llm: { provider: "anthropic", model: "claude-opus-5-5", configured: true }, documents: 1, chunks: 14 } }),
  );
  await page.route("**/api/v1/documents", (r) => r.fulfill({ json: { documents } }));
  await page.route("**/api/v1/ask/stream", (r) =>
    r.fulfill({ status: 200, headers: { "Content-Type": "text/event-stream" }, body: streamBody }),
  );
  await page.route("**/api/v1/feedback", async (r) => {
    feedback.push(r.request().postDataJSON());
    await r.fulfill({ status: 201, json: { query_id: "q_e2e", rating: "helpful", created_at: "2026-10-18T00:00:00Z" } });
  });
  return feedback;
}

test("ask a question, read the cited answer, open the source and rate it", async ({ page }) => {
  const feedback = await mockApi(
    page,
    sse([
      ["meta", { query_id: "q_e2e" }],
      ["token", { text: "Primary caregivers receive 20 weeks " }],
      ["token", { text: "of fully paid parental leave [1]." }],
      ["done", result],
    ]),
  );
  await page.goto("/");

  await expect(page.getByText("Employee Handbook")).toBeVisible();
  await expect(page.getByText("1 documents · 14 chunks · claude-opus-5-5")).toBeVisible();

  await page.getByLabel("Question").fill("How long is parental leave for primary caregivers?");
  await page.getByRole("button", { name: "Ask" }).click();

  const answer = page.getByRole("article");
  await expect(answer.getByText("Primary caregivers receive 20 weeks of fully paid parental leave")).toBeVisible();
  const chip = answer.getByRole("button", { name: "Show source 1" });
  await chip.click();
  await expect(chip).toHaveAttribute("aria-pressed", "true");

  const sources = page.getByRole("complementary", { name: "Sources" });
  await expect(sources.getByText("employee_handbook.md")).toBeVisible();
  await expect(sources.getByText("Time Off › Parental leave", { exact: false })).toBeVisible();
  await expect(sources.locator("mark", { hasText: "weeks" })).toBeVisible();

  await page.getByRole("button", { name: /Helpful/ }).first().click();
  await expect(page.getByText("Thanks for the feedback.")).toBeVisible();
  expect(feedback).toEqual([{ query_id: "q_e2e", rating: "helpful" }]);
});

test("shows the not-found state when the system abstains", async ({ page }) => {
  await mockApi(
    page,
    sse([
      ["meta", { query_id: "q_nf" }],
      ["done", { ...result, query_id: "q_nf", abstained: true, abstain_reason: "low_confidence", citations: [], answer: "I couldn't find the answer to that in the documents." }],
    ]),
  );
  await page.goto("/");
  await page.getByLabel("Question").fill("What is the CEO's salary?");
  await page.keyboard.press("Enter");
  await expect(page.getByText("Not found in your documents")).toBeVisible();
  await expect(page.getByRole("complementary", { name: "Sources" })).toHaveCount(0);
});
