import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ScoreDisplay } from "@/components/evaluation/ScoreComponents";

describe("ScoreDisplay", () => {
  it("formats proposed score over max", () => {
    render(<ScoreDisplay score={1.5} max={3} />);
    expect(screen.getByTestId("score-display")).toHaveTextContent("1.5 / 3");
  });

  it("prefers final approved when present", () => {
    render(<ScoreDisplay score={2} max={3} finalApproved={1.5} />);
    expect(screen.getByTestId("score-display")).toHaveTextContent("1.5 / 3");
  });

  it("does not render null proposed score as zero", () => {
    render(<ScoreDisplay score={null} max={3} />);
    expect(screen.getByTestId("score-display")).toHaveAttribute(
      "data-null-proposal",
      "true",
    );
    expect(screen.getByTestId("score-no-proposal")).toHaveTextContent(
      /No automatic score proposed/i,
    );
    expect(screen.getByTestId("score-display")).not.toHaveTextContent("0 / 3");
  });
});
