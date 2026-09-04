import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "@/components/layout/PageHeader";

describe("StatusBadge", () => {
  it("renders assessment ACTIVE with success styling", () => {
    render(<StatusBadge kind="assessment" state="ACTIVE" />);
    const el = screen.getByTestId("status-badge-assessment-ACTIVE");
    expect(el).toHaveTextContent(/active/i);
    expect(el.className).toMatch(/teal/);
  });

  it("renders identity REVIEW_REQUIRED as warning", () => {
    render(<StatusBadge kind="identity" state="REVIEW_REQUIRED" />);
    expect(
      screen.getByTestId("status-badge-identity-REVIEW_REQUIRED"),
    ).toHaveTextContent(/review required/i);
  });
});
