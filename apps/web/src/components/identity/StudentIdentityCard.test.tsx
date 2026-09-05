import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StudentIdentityCard } from "@/components/identity/StudentIdentityCard";

describe("StudentIdentityCard", () => {
  it("shows unresolved banner for low confidence", () => {
    render(
      <StudentIdentityCard
        rollDetected="DEMO-001"
        nameDetected="Demo Student"
        matchState="REVIEW_REQUIRED"
        confidence={0.42}
      />,
    );
    expect(screen.getByTestId("student-identity-card")).toBeInTheDocument();
    expect(screen.getByTestId("identity-unresolved-banner")).toHaveTextContent(
      /low confidence/i,
    );
  });

  it("does not show unresolved banner when confirmed with high confidence", () => {
    render(
      <StudentIdentityCard
        rollDetected="DEMO-001"
        nameDetected="Demo Student"
        matchState="CONFIRMED"
        confidence={0.95}
      />,
    );
    expect(
      screen.queryByTestId("identity-unresolved-banner"),
    ).not.toBeInTheDocument();
  });
});
