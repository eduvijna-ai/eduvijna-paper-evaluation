import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { ApiError } from "@/lib/api/http/errors";
import {
  benchmarkCaseApiToView,
  benchmarkDatasetApiToView,
  benchmarkGateVerdictApiToView,
  benchmarkRegressionCaseResultApiToView,
  benchmarkRegressionRunApiToView,
  benchmarkVersionApiToView,
  type B15BenchmarkCaseDto,
  type B15BenchmarkDatasetDto,
  type B15BenchmarkGateVerdictDto,
  type B15BenchmarkRegressionCaseResultDto,
  type B15BenchmarkRegressionRunDto,
  type B15BenchmarkVersionDto,
} from "@/lib/api/http/benchmark";
import {
  BENCHMARK_DATASET_ID,
  BENCHMARK_RUN_FAIL_ID,
  BENCHMARK_RUN_PASS_ID,
  BENCHMARK_VERSION_DRAFT_ID,
  BENCHMARK_VERSION_LOCKED_ID,
} from "@/lib/api/mock/data";
import {
  BENCHMARK_RUN_STATUSES,
  BENCHMARK_VERDICTS,
  BENCHMARK_VERSION_STATUSES,
} from "@/lib/types/enums";

const liveDatasetId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const liveVersionId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const liveRunId = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const liveCaseId = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

const datasetDto: B15BenchmarkDatasetDto = {
  id: liveDatasetId,
  code: "GOLD-UNIT",
  title: "Unit gold set",
  description: null,
  created_by: null,
  created_at: "2026-09-09T00:00:00Z",
  updated_at: "2026-09-09T00:00:00Z",
};

const versionDto: B15BenchmarkVersionDto = {
  id: liveVersionId,
  dataset_id: liveDatasetId,
  version_number: 1,
  status: "LOCKED",
  threshold_profile_snapshot: {
    profile_code: "B15_DEFAULT_V1",
    algorithm_version: "B15_V1",
    max_missing_output_rate: 0,
    max_mean_abs_score_error: 0.25,
    min_exact_score_agreement_rate: 1,
    min_taxonomy_agreement_rate: 1,
    max_safety_invariant_failure_rate: 0,
    score_tolerance: 0,
  },
  case_count: 1,
  content_hash: "a".repeat(64),
  locked_by: null,
  locked_at: "2026-09-09T01:00:00Z",
  created_by: null,
  created_at: "2026-09-09T00:00:00Z",
  updated_at: "2026-09-09T01:00:00Z",
};

const caseDto: B15BenchmarkCaseDto = {
  id: liveCaseId,
  dataset_version_id: liveVersionId,
  published_result_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
  evaluation_run_id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
  question_evaluation_id: "11111111-1111-4111-8111-111111111111",
  question_version_id: "22222222-2222-4222-8222-222222222222",
  rubric_version_id: "33333333-3333-4333-8333-333333333333",
  assessment_version_id: "44444444-4444-4444-8444-444444444444",
  expected_final_marks: "3.5",
  expected_max_marks: "5",
  expected_error_codes: ["ARITHMETIC_ERROR"],
  source_ledger_hash: "b".repeat(64),
  evidence_hash: "c".repeat(64),
  adjudicated_by: null,
  adjudicated_at: "2026-09-09T00:00:00Z",
  replay_fixture: { transcription_text: "anonymized" },
  created_at: "2026-09-09T00:00:00Z",
  updated_at: "2026-09-09T00:00:00Z",
};

const passRunDto: B15BenchmarkRegressionRunDto = {
  id: liveRunId,
  dataset_version_id: liveVersionId,
  status: "PASSED",
  verdict: "PASS",
  idempotency_key: null,
  candidate_provider: "fixed",
  candidate_model: "fixed-benchmark-pass",
  candidate_model_version: "B15_V1",
  candidate_prompt_template_version: "fixed-benchmark-v1",
  candidate_config: {},
  threshold_snapshot: versionDto.threshold_profile_snapshot,
  aggregate_metrics: {
    exact_score_agreement_rate: 1,
    mean_abs_score_error: 0,
    verdict: "PASS",
  },
  initiated_by: null,
  started_at: "2026-09-09T02:00:00Z",
  finished_at: "2026-09-09T02:00:00Z",
  failure_code: null,
  failure_detail: null,
  created_at: "2026-09-09T02:00:00Z",
  updated_at: "2026-09-09T02:00:00Z",
};

const failCaseResultDto: B15BenchmarkRegressionCaseResultDto = {
  id: "55555555-5555-4555-8555-555555555555",
  regression_run_id: liveRunId,
  benchmark_case_id: liveCaseId,
  missing_output: false,
  actual_marks: "4.5",
  actual_error_codes: ["CONCEPT_ERROR"],
  score_abs_error: "1",
  exact_score_match: false,
  taxonomy_match: false,
  safety_invariant_failed: false,
  diff: {
    expected_final_marks: "3.5",
    actual_marks: "4.5",
    expected_error_codes: ["ARITHMETIC_ERROR"],
    actual_error_codes: ["CONCEPT_ERROR"],
  },
  ai_execution_record_id: null,
  created_at: "2026-09-09T02:00:00Z",
  updated_at: "2026-09-09T02:00:00Z",
};

const passGateDto: B15BenchmarkGateVerdictDto = {
  verdict: "PASS",
  passed: true,
  run_id: liveRunId,
  status: "PASSED",
  candidate_provider: "fixed",
  candidate_model: "fixed-benchmark-pass",
  candidate_model_version: "B15_V1",
  candidate_prompt_template_version: "fixed-benchmark-v1",
  metrics: { exact_score_agreement_rate: 1 },
  threshold_snapshot: versionDto.threshold_profile_snapshot,
};

describe("B15 enums", () => {
  it("includes version, run, and verdict statuses", () => {
    expect(BENCHMARK_VERSION_STATUSES).toEqual(["DRAFT", "LOCKED"]);
    expect(BENCHMARK_RUN_STATUSES).toContain("PASSED");
    expect(BENCHMARK_RUN_STATUSES).toContain("FAILED");
    expect(BENCHMARK_VERDICTS).toEqual(["PASS", "FAIL", "PENDING"]);
  });
});

describe("B15 mappers", () => {
  it("maps dataset and version fields", () => {
    const dataset = benchmarkDatasetApiToView(datasetDto);
    expect(dataset.code).toBe("GOLD-UNIT");
    const version = benchmarkVersionApiToView(versionDto);
    expect(version.status).toBe("LOCKED");
    expect(version.threshold_profile_snapshot.profile_code).toBe(
      "B15_DEFAULT_V1",
    );
  });

  it("maps gold case marks without inventing student PII fields", () => {
    const gold = benchmarkCaseApiToView(caseDto);
    expect(gold.expected_final_marks).toBe(3.5);
    expect(gold.expected_error_codes).toEqual(["ARITHMETIC_ERROR"]);
    expect(gold).not.toHaveProperty("student_id");
    expect(gold).not.toHaveProperty("student_name");
    expect(JSON.stringify(gold)).not.toMatch(/student/i);
  });

  it("maps pass and fail verdicts distinctly", () => {
    const pass = benchmarkRegressionRunApiToView(passRunDto);
    expect(pass.verdict).toBe("PASS");
    expect(pass.status).toBe("PASSED");

    const fail = benchmarkRegressionRunApiToView({
      ...passRunDto,
      status: "FAILED",
      verdict: "FAIL",
      candidate_model: "fixed-benchmark-regress",
    });
    expect(fail.verdict).toBe("FAIL");
    expect(fail.status).toBe("FAILED");

    const gate = benchmarkGateVerdictApiToView(passGateDto);
    expect(gate.passed).toBe(true);
    expect(gate.verdict).toBe("PASS");
  });

  it("distinguishes human gold vs candidate AI in case result diffs", () => {
    const row = benchmarkRegressionCaseResultApiToView(failCaseResultDto);
    expect(row.diff.expected_final_marks).toBe("3.5");
    expect(row.diff.actual_marks).toBe("4.5");
    expect(row.actual_marks).toBe(4.5);
    expect(row.exact_score_match).toBe(false);
    expect(row.taxonomy_match).toBe(false);
  });
});

describe("B15 hybrid routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("exposes quality capability live in hybrid and mock otherwise", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(getApiCapabilities().quality).toBe("live");
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    expect(getApiCapabilities().quality).toBe("mock");
  });

  it("routes dataset list to live HTTP when quality is live", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(getApiCapabilities().quality).toBe("live");

    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [datasetDto] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await HybridEduVijnaApi.listBenchmarkDatasets!();
    expect(result.items[0]?.code).toBe("GOLD-UNIT");
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      "/api/v1/quality/benchmark-datasets",
    );
  });

  it("routes gate verdict to live HTTP", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(passGateDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const gate = await HybridEduVijnaApi.getBenchmarkGateVerdict!(liveRunId);
    expect(gate.passed).toBe(true);
    expect(String(fetchMock.mock.calls[0]?.[0])).toContain(
      `/api/v1/quality/regression-runs/${liveRunId}/gate`,
    );
  });

  it("serves demo fixtures in mock mode with DRAFT and LOCKED versions", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    const list = await HybridEduVijnaApi.listBenchmarkDatasets!();
    expect(list.items.some((d) => d.id === BENCHMARK_DATASET_ID)).toBe(true);

    const versions = await HybridEduVijnaApi.listBenchmarkVersions!(
      BENCHMARK_DATASET_ID,
    );
    expect(versions.items.some((v) => v.id === BENCHMARK_VERSION_DRAFT_ID)).toBe(
      true,
    );
    expect(
      versions.items.some((v) => v.id === BENCHMARK_VERSION_LOCKED_ID),
    ).toBe(true);
    expect(
      versions.items.find((v) => v.id === BENCHMARK_VERSION_DRAFT_ID)?.status,
    ).toBe("DRAFT");
    expect(
      versions.items.find((v) => v.id === BENCHMARK_VERSION_LOCKED_ID)?.status,
    ).toBe("LOCKED");

    const runs = await HybridEduVijnaApi.listBenchmarkRegressionRuns!(
      BENCHMARK_VERSION_LOCKED_ID,
    );
    expect(runs.items.some((r) => r.id === BENCHMARK_RUN_PASS_ID)).toBe(true);
    expect(runs.items.some((r) => r.id === BENCHMARK_RUN_FAIL_ID)).toBe(true);

    const passGate = await HybridEduVijnaApi.getBenchmarkGateVerdict!(
      BENCHMARK_RUN_PASS_ID,
    );
    expect(passGate.verdict).toBe("PASS");
    expect(passGate.passed).toBe(true);

    const failGate = await HybridEduVijnaApi.getBenchmarkGateVerdict!(
      BENCHMARK_RUN_FAIL_ID,
    );
    expect(failGate.verdict).toBe("FAIL");
    expect(failGate.passed).toBe(false);

    const failDiffs =
      await HybridEduVijnaApi.listBenchmarkRegressionCaseResults!(
        BENCHMARK_RUN_FAIL_ID,
      );
    expect(failDiffs.items[0]?.diff.expected_final_marks).toBeDefined();
    expect(failDiffs.items[0]?.actual_marks).not.toBe(
      Number(failDiffs.items[0]?.diff.expected_final_marks),
    );
  });

  it("rejects live UUIDs for B15 when quality is mock", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    expect(getApiCapabilities().quality).toBe("mock");

    await expect(
      HybridEduVijnaApi.getBenchmarkDataset!(liveDatasetId),
    ).rejects.toMatchObject({ code: "B15_MOCK_DEMO_ONLY" });

    await expect(
      HybridEduVijnaApi.listBenchmarkVersions!(liveDatasetId),
    ).rejects.toMatchObject({ code: "B15_MOCK_DEMO_ONLY" });

    await expect(
      HybridEduVijnaApi.getBenchmarkRegressionRun!(liveRunId),
    ).rejects.toMatchObject({ code: "B15_MOCK_DEMO_ONLY" });

    await expect(
      HybridEduVijnaApi.getBenchmarkGateVerdict!(liveRunId),
    ).rejects.toMatchObject({ code: "B15_MOCK_DEMO_ONLY" });
  });

  it("propagates live HTTP errors without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "NOT_FOUND", message: "Benchmark dataset not found" },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      HybridEduVijnaApi.getBenchmarkDataset!(liveDatasetId),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
