import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import AnswerView, { linkCitations } from "./AnswerView";
import AskBox from "./AskBox";

it("links citation markers but not existing markdown links", () => {
  expect(linkCitations("Leave is 20 weeks [1][2].")).toBe("Leave is 20 weeks [1](#cite-1)[2](#cite-2).");
  expect(linkCitations("See [docs](http://x)")).toBe("See [docs](http://x)");
});

it("renders citation chips that select a source", async () => {
  const onSelect = vi.fn();
  render(
    <AnswerView
      text="Primary caregivers get 20 weeks [1]. Secondary get 8 [3]."
      streaming={false}
      activeCitation={1}
      availableCitations={new Set([1])}
      onSelectCitation={onSelect}
    />,
  );
  const chip = screen.getByRole("button", { name: "Show source 1" });
  expect(chip).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(chip);
  expect(onSelect).toHaveBeenCalledWith(1);
  expect(screen.getByRole("button", { name: "Show source 3" })).toBeDisabled();
});

it("submits on Enter and offers Stop while streaming", async () => {
  const onAsk = vi.fn();
  const onStop = vi.fn();
  const { rerender } = render(<AskBox streaming={false} onAsk={onAsk} onStop={onStop} />);
  expect(screen.getByRole("button", { name: "Ask" })).toBeDisabled();
  await userEvent.type(screen.getByLabelText("Question"), "  How long is leave?{Enter}");
  expect(onAsk).toHaveBeenCalledWith("How long is leave?");

  rerender(<AskBox streaming onAsk={onAsk} onStop={onStop} />);
  await userEvent.click(screen.getByRole("button", { name: "Stop" }));
  expect(onStop).toHaveBeenCalled();
});
