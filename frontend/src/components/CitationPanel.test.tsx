import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, vi } from "vitest";
import type { Citation } from "../api/client";
import { mockFetch, renderWithQuery } from "../test/utils";
import CitationPanel, { highlight, sentencesCiting } from "./CitationPanel";
import Feedback from "./Feedback";
import NotFoundState from "./NotFoundState";

const citations: Citation[] = [
  {
    n: 1,
    chunk_id: "c1",
    doc_id: "hr",
    file_name: "HR_Handbook.pdf",
    page: 14,
    section_path: ["Time Off", "Parental leave"],
    snippet: "Primary caregivers receive 20 weeks of fully paid parental leave.",
  },
  { n: 2, chunk_id: "c2", doc_id: "hr", file_name: "it.txt", page: null, section_path: [], snippet: "Laptops." },
];
const answer = "Primary caregivers get 20 weeks of paid leave [1]. Laptops are refreshed [2].";

afterEach(() => vi.unstubAllGlobals());

it("finds the sentences citing an excerpt", () => {
  expect(sentencesCiting(answer, 1)).toEqual(["Primary caregivers get 20 weeks of paid leave [1]."]);
  expect(sentencesCiting("A [1][2]. B [2].", 2)).toEqual(["A [1][2].", "B [2]."]);
});

it("highlights terms shared with the citing sentence", () => {
  render(<p>{highlight(citations[0].snippet, sentencesCiting(answer, 1))}</p>);
  const marked = Array.from(document.querySelectorAll("mark")).map((m) => m.textContent);
  expect(marked).toEqual(["Primary", "caregivers", "20", "weeks", "paid", "leave"]);
  expect(highlight("text", [])).toEqual(["text"]);
});

it("shows file, page and section, and selects sources", async () => {
  const onSelect = vi.fn();
  render(<CitationPanel citations={citations} active={1} answer={answer} onSelect={onSelect} />);
  expect(screen.getByText("HR_Handbook.pdf")).toBeInTheDocument();
  expect(screen.getByText("p. 14")).toBeInTheDocument();
  expect(screen.getByText("Time Off › Parental leave")).toBeInTheDocument();
  await userEvent.click(screen.getByText("it.txt"));
  expect(onSelect).toHaveBeenCalledWith(2);
});

it("renders nothing without citations", () => {
  const { container } = render(<CitationPanel citations={[]} active={null} answer="" onSelect={() => {}} />);
  expect(container).toBeEmptyDOMElement();
});

it("explains why the system abstained", () => {
  render(<NotFoundState reason="citation_check_failed" />);
  expect(screen.getByRole("status")).toHaveTextContent("couldn't be fully supported with citations");
  render(<NotFoundState reason={null} />);
  expect(screen.getAllByRole("status")[1]).toHaveTextContent("don't cover this question");
});

it("posts feedback once", async () => {
  const fetch = mockFetch({ "/feedback": { query_id: "q_1", rating: "helpful" } });
  renderWithQuery(<Feedback queryId="q_1" />);
  await userEvent.click(screen.getByRole("button", { name: /Helpful/ }));
  expect(await screen.findByText("Thanks for the feedback.")).toBeInTheDocument();
  expect(JSON.parse(fetch.mock.calls[0][1]!.body as string)).toEqual({ query_id: "q_1", rating: "helpful" });
});
