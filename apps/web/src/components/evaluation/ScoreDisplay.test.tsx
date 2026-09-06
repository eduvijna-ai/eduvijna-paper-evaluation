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
});
