import { afterEach, describe, expect, it, vi } from "vitest";
import {
  annotationsToEvidenceRegions,
  publicationWorkspaceApiToView,
  type B7PublicationWorkspaceDto,
} from "@/lib/api/http/publication";
import {
  parentReportApiToView,
  studentReportApiToView,
  teacherReportApiToView,
  type B7ParentReportDto,
  type B7StudentReportDto,
  type B7TeacherReportDto,
} from "@/lib/api/http/reports";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { ApiError } from "@/lib/api/http/errors";

const workspaceDto: B7PublicationWorkspaceDto = {
  submission_id: "11111111-1111-4111-8111-111111111111",
  workflow_state: "APPROVED",
  latest: {
    id: "22222222-2222-4222-8222-222222222222",
    submission_id: "11111111-1111-4111-8111-111111111111",
    student_id: "33333333-3333-4333-8333-333333333333",
    assessment_id: "44444444-4444-4444-8444-444444444444",
    assessment_version_id: "55555555-5555-4555-8555-555555555555",
    evaluation_run_id: "66666666-6666-4666-8666-666666666666",
    version_number: 1,
    status: "GENERATED",
    ledger_snapshot_hash: "a".repeat(64),
    total_score: "7.5",
    max_total_score: "10.00",
    narrative_source: "FIXED",
    generated_at: "2026-09-07T00:00:00Z",
    published_at: null,
    failure_code: null,
    failure_detail: null,
    artifacts: {
      ANNOTATED_PDF: { available: true, sha256: "b".repeat(64), byte_size: 100 },
    },
  },
  versions: [],
  annotations: [
    {
      id: "ann-1",
      annotation_type: "MARK",
      submission_page_id: "page-uuid-1",
      question_evaluation_id: "qe-1",
      answer_region_id: "reg-1",
      x: 0.1,
      y: 0.2,
      width: 0.3,
      height: 0.1,
      payload: { final_marks: 3.5, max_marks: 5, reason: "Override" },
      source_type: "LEDGER",
    },
  ],
};

const studentDto: B7StudentReportDto = {
  published_result_id: "22222222-2222-4222-8222-222222222222",
  student: { id: "33333333-3333-4333-8333-333333333333", display_name: "Ada" },
  assessment: {
    id: "44444444-4444-4444-8444-444444444444",
    title: "Midterm",
    code: "MT",
    assessment_version_id: "55555555-5555-4555-8555-555555555555",
  },
  total_score: 7.5,
  max_total_score: 10,
  percentage: 75,
  questions: [
    {
      question_id: "q1",
      question_code: "Q1",
      final_score: 3.5,
      max_mark: 5,
      feedback: "Good",
      error_explanations: [],
      corrected_approach: "Check arithmetic",
    },
  ],
  strengths: ["Setup"],
  areas_for_improvement: ["Arithmetic"],
  next_steps: ["Practice"],
  ledger_snapshot_hash: "a".repeat(64),
  narrative_source: "FIXED",
};

describe("B7 publication capability", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("marks publication and reports live in hybrid", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const caps = getApiCapabilities();
    expect(caps.evaluation).toBe("live");
    expect(caps.publication).toBe("live");
    expect(caps.reports).toBe("live");
    expect(caps.analytics).toBe("mock");
    expect(caps.learning).toBe("mock");
  });

  it("keeps publication and reports mock in mock mode", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    const caps = getApiCapabilities();
    expect(caps.publication).toBe("mock");
    expect(caps.reports).toBe("mock");
  });
});

describe("B7 publication mappers", () => {
  it("maps workspace without proposed_ai_score in annotations", () => {
    const view = publicationWorkspaceApiToView(workspaceDto);
    expect(view.latest?.status).toBe("GENERATED");
    expect(view.latest?.total_score).toBe(7.5);
    expect(view.annotations[0]?.payload.final_marks).toBe(3.5);
    expect(view.annotations[0]?.payload).not.toHaveProperty("proposed_ai_score");
  });

  it("converts annotations to evidence regions using final marks", () => {
    const view = publicationWorkspaceApiToView(workspaceDto);
    const regions = annotationsToEvidenceRegions(
      view.annotations,
      new Map([["page-uuid-1", 1]]),
    );
    expect(regions[0]?.label).toBe("3.5/5");
    expect(regions[0]?.annotation_kind).toBe("PARTIAL");
  });

  it("maps student report with final scores only and empty topic_focus", () => {
    const report = studentReportApiToView(studentDto);
    expect(report.live_published).toBe(true);
    expect(report.topic_focus).toEqual([]);
    expect(report.question_summaries[0]?.final_score).toBe(3.5);
    expect(report.question_summaries[0]?.proposed_score).toBe(3.5);
    expect(report.weaknesses).toEqual(["Arithmetic"]);
    expect(JSON.stringify(report)).not.toMatch(/proposed_ai_score/);
  });

  it("maps parent how_family_can_help to how_to_help", () => {
    const dto: B7ParentReportDto = {
      published_result_id: studentDto.published_result_id,
      student_display_name: "Ada",
      assessment_title: "Midterm",
      total_score: 7.5,
      max_total_score: 10,
      percentage: 75,
      what_went_well: ["A"],
      what_to_practice: ["B"],
      how_family_can_help: ["Help with drills"],
      next_step: "Review",
      ledger_snapshot_hash: "a".repeat(64),
      narrative_source: "FIXED",
    };
    const report = parentReportApiToView(dto);
    expect(report.how_to_help).toEqual(["Help with drills"]);
    expect(report.live_published).toBe(true);
  });

  it("maps teacher report final scores", () => {
    const dto: B7TeacherReportDto = {
      published_result_id: studentDto.published_result_id,
      student: studentDto.student,
      assessment: studentDto.assessment,
      total_score: 7.5,
      max_total_score: 10,
      questions: [
        {
          question_id: "q1",
          question_code: "Q1",
          final_score: 3.5,
          max_mark: 5,
          workflow_state: "OVERRIDDEN",
          criterion_decisions: [],
          error_codes: ["CALCULATION"],
        },
      ],
      ledger_snapshot_hash: "a".repeat(64),
    };
    const report = teacherReportApiToView(dto);
    expect(report.questions[0]?.final_score).toBe(3.5);
    expect(report.questions[0]?.workflow_state).toBe("OVERRIDDEN");
  });
});

describe("B7 hybrid refuse mock analytics/learning for live UUIDs", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("refuses analytics for live UUID even when reports are live", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    await expect(
      HybridEduVijnaApi.getAssessmentAnalytics(
        "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      ),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("refuses learning for live UUID", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    await expect(
      HybridEduVijnaApi.getAdaptiveLearning(
        "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      ),
    ).rejects.toMatchObject({ code: "LEARNING_NOT_LIVE" });
  });
});
