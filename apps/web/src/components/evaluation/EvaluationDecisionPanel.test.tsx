import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { EvaluationDecisionPanel } from "@/components/evaluation/EvaluationDecisionPanel";
import type { EvaluationLedger } from "@/lib/types/domain";

const ledger: EvaluationLedger = {
  id: "led-test",
  tenant_id: "t",
  evaluation_run_id: "run",
  submission_id: "sub",
  student_id: "stu",
  assessment_id: "assess",
  assessment_version_id: "av",
  question_id: "q-1b",
  question_version_id: "qv",
  rubric_version_id: "rv",
  answer_key_version_id: "akv",
  answer_region_ids: ["reg-2"],
  max_mark: 3,
  criterion_decisions: [
    {
      rubric_criterion_id: "rub-1",
      criterion_label: "Roots",
      max_marks: 2,
      proposed_marks: 1,
      final_marks: null,
      decision: "PARTIAL",
      error_code: "CALCULATION",
      deduction_reason: "One root wrong",
      step_index: 1,
    },
  ],
  proposed_ai_score: 1.5,
  final_human_approved_score: null,
  error_codes: ["CALCULATION"],
  ecf_applied: true,
  identity_confidence: 0.9,
  mapping_confidence: 0.8,
  transcription_confidence: 0.7,
  evaluation_confidence: 0.6,
  math_verification_confidence: null,
  workflow_state: "REVIEW_REQUIRED",
  ledger_version: 1,
  feedback_draft: "Check arithmetic",
  corrected_approach: "x = 2 or 3",
  teacher_notes: null,
};

describe("EvaluationDecisionPanel", () => {
  it("renders separate confidence dimensions and ECF", () => {
    render(
      <EvaluationDecisionPanel ledger={ledger} onAction={vi.fn()} />,
    );
    expect(screen.getByTestId("evaluation-decision-panel")).toBeInTheDocument();
    expect(screen.getByTestId("confidence-dimensions")).toHaveTextContent(
      /identity/i,
    );
    expect(screen.getByTestId("confidence-dimensions")).toHaveTextContent(
      /mapping/i,
    );
    expect(screen.getByTestId("confidence-dimensions")).toHaveTextContent(
      /transcription/i,
    );
    expect(screen.getByTestId("confidence-dimensions")).toHaveTextContent(
      /evaluation/i,
    );
    expect(screen.getByTestId("score-display")).toHaveTextContent("1.5 / 3");
    expect(screen.getByTestId("ecf-applied")).toBeInTheDocument();
    expect(screen.getByTestId("teacher-review-actions")).toBeInTheDocument();
  });
});
