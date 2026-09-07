import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import {
  assessmentAnalyticsApiToView,
  studentAnalyticsApiToView,
  type B8AssessmentAnalyticsDto,
  type B8StudentAnalyticsDto,
} from "@/lib/api/http/analytics";
import { ApiError } from "@/lib/api/http/errors";
import {
  formatAnalyticsPassRate,
  isLiveAssessmentAnalytics,
  isLiveStudentAnalytics,
} from "@/lib/types/domain";

const assessmentDto: B8AssessmentAnalyticsDto = {
  assessment: {
    id: "44444444-4444-4444-8444-444444444444",
    code: "MT",
    title: "Midterm",
    curriculum_id: "55555555-5555-4555-8555-555555555555",
    status: "PUBLISHED",
  },
  class_section_id: null,
  published_attempt_count: 3,
  unique_student_count: 2,
  mean_percentage: 72.5,
  median_percentage: 70,
  pass_threshold_percent: null,
  pass_rate: null,
  score_distribution: [
    { lower_bound: 0, upper_bound: 20, count: 0 },
    { lower_bound: 20, upper_bound: 40, count: 0 },
    { lower_bound: 40, upper_bound: 60, count: 1 },
    { lower_bound: 60, upper_bound: 80, count: 1 },
    { lower_bound: 80, upper_bound: 100, count: 1 },
  ],
  question_performance: [
    {
      question_id: "q1",
      question_code: "Q1",
      question_version_ids: ["qv1"],
      attempt_count: 3,
      blank_count: 0,
      mean_score_percent: 80,
      median_score_percent: 80,
      full_credit_count: 2,
      zero_score_count: 0,
      common_errors: [{ code: "CALCULATION", count: 1 }],
    },
  ],
  error_distribution: {
    academic: [{ code: "CALCULATION", count: 2, category: "academic" }],
    review_conditions: [
      { code: "UNREADABLE", count: 1, category: "review_condition" },
    ],
  },
  curriculum_performance: [],
  mapped_scorable_question_count: 1,
  unmapped_scorable_question_count: 0,
  mastery_coverage_ratio: 1,
  source: "PUBLISHED_LEDGER",
  as_of: "2026-09-07T00:00:00Z",
};

const studentDto: B8StudentAnalyticsDto = {
  student: {
    id: "33333333-3333-4333-8333-333333333333",
    display_name: "Ada",
    student_code: "S1",
    external_ref: "S1",
  },
  published_assessment_count: 2,
  published_attempt_count: 2,
  average_percentage: 68,
  concept_signals: [
    {
      curriculum_node_id: "n1",
      code: "ALG",
      title: "Algebra",
      node_type: "TOPIC",
      concept: {
        strong_count: 1,
        weak_count: 0,
        inconclusive_count: 0,
        signal: "STRONG",
      },
      execution: {
        strong_count: 0,
        weak_count: 1,
        inconclusive_count: 0,
        signal: "WEAK",
      },
      procedure: {
        strong_count: 0,
        weak_count: 0,
        inconclusive_count: 1,
        signal: "INCONCLUSIVE",
      },
      evidence_count: 3,
      mean_score_ratio: 0.75,
    },
  ],
  error_distribution: [{ code: "METHOD", count: 2 }],
  mastery_coverage: {
    curriculum_node_count: 1,
    evidence_row_count: 3,
  },
  materialization_status: "READY",
  published_result_count: 2,
  materialized_result_count: 2,
  source: "PUBLISHED_LEDGER",
  as_of: "2026-09-07T00:00:00Z",
};

describe("B8 analytics capability", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("marks analytics and learning live in hybrid", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const caps = getApiCapabilities();
    expect(caps.analytics).toBe("live");
    expect(caps.learning).toBe("live");
    expect(caps.publication).toBe("live");
    expect(caps.reports).toBe("live");
  });

  it("keeps analytics mock in mock mode", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    expect(getApiCapabilities().analytics).toBe("mock");
    expect(getApiCapabilities().learning).toBe("mock");
  });
});

describe("B8 pass rate helpers", () => {
  it("renders Not configured when threshold is null", () => {
    expect(formatAnalyticsPassRate(null, null)).toBe("Not configured");
    expect(formatAnalyticsPassRate(0.8, null)).toBe("Not configured");
    expect(formatAnalyticsPassRate(undefined, undefined)).toBe(
      "Not configured",
    );
  });

  it("renders percentage when threshold and rate are set", () => {
    expect(formatAnalyticsPassRate(0.78, 40)).toBe("78%");
  });
});

describe("B8 analytics mappers", () => {
  it("maps live assessment analytics with question_performance not difficulty", () => {
    const view = assessmentAnalyticsApiToView(assessmentDto);
    expect(isLiveAssessmentAnalytics(view)).toBe(true);
    expect(view.source).toBe("PUBLISHED_LEDGER");
    expect(view.question_performance).toHaveLength(1);
    expect(view.question_performance[0]?.question_code).toBe("Q1");
    expect(view.pass_rate).toBeNull();
    expect(view.pass_threshold_percent).toBeNull();
    expect(JSON.stringify(view)).not.toMatch(/question_difficulty/);
    expect(view.error_distribution.academic[0]?.code).toBe("CALCULATION");
    expect(view.error_distribution.review_conditions[0]?.code).toBe(
      "UNREADABLE",
    );
  });

  it("maps live student analytics without recurring_errors or mastery_trend", () => {
    const view = studentAnalyticsApiToView(studentDto);
    expect(isLiveStudentAnalytics(view)).toBe(true);
    expect(view.concept_signals).toHaveLength(1);
    expect(view.error_distribution[0]?.code).toBe("METHOD");
    expect(view.materialization_status).toBe("READY");
    expect(JSON.stringify(view)).not.toMatch(/recurring_errors/);
    expect(JSON.stringify(view)).not.toMatch(/mastery_trend/);
    expect(JSON.stringify(view)).not.toMatch(/"trend"/);
  });
});

describe("B8 hybrid analytics routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("routes assessment analytics to live HTTP without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(assessmentDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await HybridEduVijnaApi.getAssessmentAnalytics(
      "44444444-4444-4444-8444-444444444444",
      { passThresholdPercent: 40 },
    );

    expect(isLiveAssessmentAnalytics(result)).toBe(true);
    expect(fetchMock).toHaveBeenCalled();
    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).toContain("/api/v1/analytics/assessments/");
    expect(url).toContain("pass_threshold_percent=40");
    expect(JSON.stringify(result)).toContain("question_performance");
    expect(JSON.stringify(result)).not.toContain("question_difficulty");
  });

  it("routes student analytics to live HTTP without calling learning", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(studentDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await HybridEduVijnaApi.getStudentAnalytics(
      "33333333-3333-4333-8333-333333333333",
    );

    expect(isLiveStudentAnalytics(result)).toBe(true);
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.includes("/api/v1/analytics/students/"))).toBe(
      true,
    );
    expect(urls.some((u) => u.includes("/learning"))).toBe(false);
  });

  it("surfaces live analytics HTTP errors without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: { code: "NOT_FOUND", message: "Assessment not found" },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      HybridEduVijnaApi.getAssessmentAnalytics(
        "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      ),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
