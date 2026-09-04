import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RubricCriterionRow } from "@/components/evaluation/ScoreComponents";

describe("RubricCriterionRow", () => {
  it("shows Full credit with glyph text not color alone", () => {
    render(
      <ul>
        <RubricCriterionRow
          criterion={{
            rubric_criterion_id: "rub-1a",
            criterion_label: "Discriminant formula",
            max_marks: 1,
            proposed_marks: 1,
            final_marks: null,
            decision: "AWARDED",
            error_code: null,
            deduction_reason: null,
            step_index: 0,
          }}
        />
      </ul>,
    );
    const row = screen.getByTestId("rubric-criterion-rub-1a");
    expect(row).toHaveTextContent("Full credit");
    expect(row).toHaveTextContent("✓");
  });

  it("shows Partial and Mark lost labels", () => {
    const { rerender } = render(
      <ul>
        <RubricCriterionRow
          criterion={{
            rubric_criterion_id: "rub-p",
            criterion_label: "Setup",
            max_marks: 2,
            proposed_marks: 1,
            final_marks: null,
            decision: "PARTIAL",
            error_code: "METHOD",
            deduction_reason: "Ratio inverted",
            step_index: 0,
          }}
        />
      </ul>,
    );
    expect(screen.getByTestId("rubric-criterion-rub-p")).toHaveTextContent(
      "Partial credit",
    );

    rerender(
      <ul>
        <RubricCriterionRow
          criterion={{
            rubric_criterion_id: "rub-d",
            criterion_label: "Final",
            max_marks: 2,
            proposed_marks: 0,
            final_marks: null,
            decision: "DEDUCTED",
            error_code: "CALCULATION",
            deduction_reason: "Wrong value",
            step_index: 1,
          }}
        />
      </ul>,
    );
    expect(screen.getByTestId("rubric-criterion-rub-d")).toHaveTextContent(
      "Mark lost",
    );
  });
});
