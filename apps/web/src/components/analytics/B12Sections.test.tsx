import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { B12Sections } from "@/components/analytics/B12Sections";

vi.mock("@/lib/api", () => ({
  api: {
    getStudentMasteryState: vi.fn().mockResolvedValue({
      student_id: "student-demo-001",
      items: [
        {
          id: "ms-1",
          curriculum_node_id: "n1",
          curriculum_id: "c1",
          code: "DISC",
          title: "Discriminant",
          node_type: "TOPIC",
          concept_mastery: 0.8,
          execution_accuracy: null,
          concept_decisive_count: 2,
          execution_decisive_count: 0,
          concept_inconclusive_count: 0,
          execution_inconclusive_count: 1,
          evidence_count: 3,
          insufficient_concept_evidence: false,
          insufficient_execution_evidence: true,
          source_evidence_hash: "h",
          algorithm_version: "B12_V1",
          last_updated_at: "2026-09-07T00:00:00Z",
        },
      ],
      algorithm_version: "B12_V1",
      source: "MASTERY_EVIDENCE",
      as_of: "2026-09-07T00:00:00Z",
    }),
    getStudentMasteryTrend: vi.fn().mockResolvedValue({
      student_id: "student-demo-001",
      curriculum_node_id: null,
      points: [
        {
          curriculum_node_id: "n1",
          curriculum_id: "c1",
          code: "DISC",
          title: "Discriminant",
          published_result_id: "pr1",
          assessment_id: "a1",
          assessment_code: "UT-1",
          effective_at: "2026-08-01T00:00:00Z",
          concept_mastery: 0.5,
          execution_accuracy: 0.4,
          concept_decisive_count: 1,
          execution_decisive_count: 1,
          evidence_count: 1,
          insufficient_concept_evidence: false,
          insufficient_execution_evidence: false,
          source_evidence_hash: "h",
          algorithm_version: "B12_V1",
        },
      ],
      algorithm_version: "B12_V1",
      source: "MASTERY_EVIDENCE",
      as_of: "2026-09-07T00:00:00Z",
    }),
    getStudentRepeatedErrors: vi.fn().mockResolvedValue({
      student_id: "student-demo-001",
      items: [
        {
          error_code: "CALCULATION",
          occurrence_count: 2,
          distinct_published_result_count: 2,
          distinct_assessment_count: 2,
          first_seen_at: "2026-08-01T00:00:00Z",
          last_seen_at: "2026-09-01T00:00:00Z",
          affected_question_evaluations: [],
          curriculum_node_ids: [],
        },
      ],
      recurrence_threshold: 2,
      algorithm_version: "B12_V1",
      source: "MASTERY_EVIDENCE",
      as_of: "2026-09-07T00:00:00Z",
    }),
    getStudentRecoverableMarks: vi.fn().mockResolvedValue({
      student_id: "student-demo-001",
      total_lost_marks: "5.00",
      attributed_potentially_recoverable_marks: "3.00",
      unattributed_lost_marks: "2.00",
      items: [],
      disclaimer:
        "Potentially recoverable marks are an analytical estimate from final criterion deductions, not guaranteed recovery.",
      algorithm_version: "B12_V1",
      source: "PUBLISHED_LEDGER",
      as_of: "2026-09-07T00:00:00Z",
    }),
    getStudentMistakeNotebook: vi.fn().mockResolvedValue({
      student_id: "student-demo-001",
      entries: [
        {
          id: "nb1",
          published_result_id: "pr1",
          assessment_id: "a1",
          assessment_code: "UT-1",
          submission_id: "s1",
          question_evaluation_id: "qe1",
          question_version_id: "qv1",
          question_code: "Q1",
          academic_error_code: "CALCULATION",
          final_score: "2.00",
          max_mark: "5.00",
          deduction_reasons: ["slip"],
          first_divergence_step: "1",
          curriculum_nodes: [],
          recommended_practice_kind: "EXECUTION_PRACTICE",
          linked_learning_recommendation_ids: [],
          source_ledger_snapshot_hash: "h",
          algorithm_version: "B12_V1",
          materialized_at: "2026-09-07T00:00:00Z",
          effective_at: "2026-08-01T00:00:00Z",
        },
      ],
      algorithm_version: "B12_V1",
      source: "PUBLISHED_LEDGER",
      as_of: "2026-09-07T00:00:00Z",
    }),
  },
}));

vi.mock("@/lib/api/capabilities", () => ({
  getApiCapabilities: () => ({
    analytics: "mock",
    learning: "mock",
  }),
}));

function renderB12() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <B12Sections studentId="student-demo-001" />
    </QueryClientProvider>,
  );
}

describe("B12Sections", () => {
  it("renders all four B12 section testids with longitudinal vs evidence distinction", async () => {
    renderB12();
    expect(await screen.findByTestId("b12-longitudinal-mastery")).toBeTruthy();
    expect(screen.getByTestId("b12-repeated-errors")).toBeTruthy();
    expect(screen.getByTestId("b12-recoverable-marks")).toBeTruthy();
    expect(screen.getByTestId("b12-mistake-notebook")).toBeTruthy();
    expect(await screen.findByText(/B12_V1/)).toBeTruthy();
    expect(await screen.findByText(/Insufficient evidence/i)).toBeTruthy();
    expect(
      (await screen.findByTestId("b12-recoverable-disclaimer")).textContent,
    ).toMatch(/analytical estimate/i);
    expect(screen.queryByText(/assign resource/i)).toBeNull();
  });
});
