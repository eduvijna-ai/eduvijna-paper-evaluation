import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfidenceIndicator } from "@/components/ui/FeedbackStates";

describe("ConfidenceIndicator", () => {
  it("marks low confidence as unresolved", () => {
    render(<ConfidenceIndicator value={0.4} label="Identity confidence" />);
    const el = screen.getByTestId("confidence-indicator");
    expect(el).toHaveAttribute("data-unresolved", "true");
    expect(el).toHaveTextContent(/unresolved/i);
    expect(el).toHaveTextContent("Identity confidence");
  });

  it("shows high confidence without unresolved flag", () => {
    render(<ConfidenceIndicator value={0.92} />);
    const el = screen.getByTestId("confidence-indicator");
    expect(el).toHaveAttribute("data-unresolved", "false");
    expect(el).toHaveAttribute("data-level", "high");
  });
});
