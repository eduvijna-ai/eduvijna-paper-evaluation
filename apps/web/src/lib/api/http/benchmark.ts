import type {
  BenchmarkCase,
  BenchmarkCaseCreate,
  BenchmarkCaseList,
  BenchmarkDataset,
  BenchmarkDatasetCreate,
  BenchmarkDatasetList,
  BenchmarkEligibleSources,
  BenchmarkGateVerdict,
  BenchmarkRegressionCaseResult,
  BenchmarkRegressionCaseResultList,
  BenchmarkRegressionRun,
  BenchmarkRegressionRunCreate,
  BenchmarkRegressionRunList,
  BenchmarkThresholdProfile,
  BenchmarkVersion,
  BenchmarkVersionCreate,
  BenchmarkVersionList,
} from "@/lib/types/domain";
import { httpRequest } from "./client";

function asNumber(
  value: number | string | null | undefined,
): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function asNumberRequired(
  value: number | string | null | undefined,
  fallback = 0,
): number {
  return asNumber(value) ?? fallback;
}

export interface B15BenchmarkThresholdProfileDto {
  profile_code?: string;
  algorithm_version?: string;
  max_missing_output_rate?: number;
  max_mean_abs_score_error?: number;
  min_exact_score_agreement_rate?: number;
  min_taxonomy_agreement_rate?: number;
  max_safety_invariant_failure_rate?: number;
  score_tolerance?: number;
  [key: string]: unknown;
}

export interface B15BenchmarkDatasetDto {
  id: string;
  code: string;
  title: string;
  description?: string | null;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface B15BenchmarkDatasetListDto {
  items?: B15BenchmarkDatasetDto[];
}

export interface B15BenchmarkVersionDto {
  id: string;
  dataset_id: string;
  version_number: number;
  status: string;
  threshold_profile_snapshot?: B15BenchmarkThresholdProfileDto | Record<string, unknown>;
  case_count?: number;
  content_hash?: string | null;
  locked_by?: string | null;
  locked_at?: string | null;
  created_by?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface B15BenchmarkVersionListDto {
  items?: B15BenchmarkVersionDto[];
}

export interface B15BenchmarkCaseDto {
  id: string;
  dataset_version_id: string;
  published_result_id: string;
  evaluation_run_id: string;
  question_evaluation_id: string;
  question_version_id: string;
  rubric_version_id: string;
  assessment_version_id: string;
  expected_final_marks: number | string;
  expected_max_marks: number | string;
  expected_error_codes?: string[];
  source_ledger_hash: string;
  evidence_hash: string;
  adjudicated_by?: string | null;
  adjudicated_at?: string;
  replay_fixture?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string;
}

export interface B15BenchmarkCaseListDto {
  items?: B15BenchmarkCaseDto[];
}

export interface B15EligibleQuestionEvaluationDto {
  question_evaluation_id: string;
  question_version_id: string;
  workflow_state: string;
  final_human_approved_score: number | string;
  max_mark: number | string;
  error_codes?: string[];
}

export interface B15EligibleSourceDto {
  published_result_id: string;
  evaluation_run_id: string;
  submission_id: string;
  assessment_version_id: string;
  ledger_snapshot_hash: string;
  question_evaluations?: B15EligibleQuestionEvaluationDto[];
}

export interface B15EligibleSourcesDto {
  items?: B15EligibleSourceDto[];
}

export interface B15BenchmarkRegressionRunDto {
  id: string;
  dataset_version_id: string;
  status: string;
  verdict: string;
  idempotency_key?: string | null;
  candidate_provider: string;
  candidate_model: string;
  candidate_model_version: string;
  candidate_prompt_template_version: string;
  candidate_config?: Record<string, unknown>;
  threshold_snapshot?: Record<string, unknown>;
  aggregate_metrics?: Record<string, unknown>;
  initiated_by?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  failure_code?: string | null;
  failure_detail?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface B15BenchmarkRegressionRunListDto {
  items?: B15BenchmarkRegressionRunDto[];
}

export interface B15BenchmarkRegressionCaseResultDto {
  id: string;
  regression_run_id: string;
  benchmark_case_id: string;
  missing_output: boolean;
  actual_marks?: number | string | null;
  actual_error_codes?: string[];
  score_abs_error?: number | string | null;
  exact_score_match: boolean;
  taxonomy_match?: boolean | null;
  safety_invariant_failed: boolean;
  diff?: Record<string, unknown>;
  ai_execution_record_id?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface B15BenchmarkRegressionCaseResultListDto {
  items?: B15BenchmarkRegressionCaseResultDto[];
}

export interface B15BenchmarkGateVerdictDto {
  verdict: string;
  passed: boolean;
  run_id: string;
  status?: string;
  candidate_provider: string;
  candidate_model: string;
  candidate_model_version: string;
  candidate_prompt_template_version: string;
  metrics?: Record<string, unknown>;
  threshold_snapshot?: Record<string, unknown>;
}

const DEFAULT_THRESHOLDS: BenchmarkThresholdProfile = {
  profile_code: "B15_DEFAULT_V1",
  algorithm_version: "B15_V1",
  max_missing_output_rate: 0,
  max_mean_abs_score_error: 0.25,
  min_exact_score_agreement_rate: 1,
  min_taxonomy_agreement_rate: 1,
  max_safety_invariant_failure_rate: 0,
  score_tolerance: 0,
};

export function benchmarkThresholdProfileApiToView(
  dto?: B15BenchmarkThresholdProfileDto | Record<string, unknown> | null,
): BenchmarkThresholdProfile {
  const raw = (dto ?? {}) as B15BenchmarkThresholdProfileDto;
  return {
    profile_code: String(raw.profile_code ?? DEFAULT_THRESHOLDS.profile_code),
    algorithm_version: String(
      raw.algorithm_version ?? DEFAULT_THRESHOLDS.algorithm_version,
    ),
    max_missing_output_rate: asNumberRequired(
      raw.max_missing_output_rate as number | string | undefined,
      DEFAULT_THRESHOLDS.max_missing_output_rate,
    ),
    max_mean_abs_score_error: asNumberRequired(
      raw.max_mean_abs_score_error as number | string | undefined,
      DEFAULT_THRESHOLDS.max_mean_abs_score_error,
    ),
    min_exact_score_agreement_rate: asNumberRequired(
      raw.min_exact_score_agreement_rate as number | string | undefined,
      DEFAULT_THRESHOLDS.min_exact_score_agreement_rate,
    ),
    min_taxonomy_agreement_rate: asNumberRequired(
      raw.min_taxonomy_agreement_rate as number | string | undefined,
      DEFAULT_THRESHOLDS.min_taxonomy_agreement_rate,
    ),
    max_safety_invariant_failure_rate: asNumberRequired(
      raw.max_safety_invariant_failure_rate as number | string | undefined,
      DEFAULT_THRESHOLDS.max_safety_invariant_failure_rate,
    ),
    score_tolerance: asNumberRequired(
      raw.score_tolerance as number | string | undefined,
      DEFAULT_THRESHOLDS.score_tolerance,
    ),
  };
}

export function benchmarkDatasetApiToView(
  dto: B15BenchmarkDatasetDto,
): BenchmarkDataset {
  return {
    id: dto.id,
    code: dto.code,
    title: dto.title,
    description: dto.description ?? null,
    created_by: dto.created_by ?? null,
    created_at: dto.created_at ?? new Date().toISOString(),
    updated_at: dto.updated_at ?? new Date().toISOString(),
  };
}

export function benchmarkDatasetListApiToView(
  dto: B15BenchmarkDatasetListDto,
): BenchmarkDatasetList {
  return { items: (dto.items ?? []).map(benchmarkDatasetApiToView) };
}

export function benchmarkVersionApiToView(
  dto: B15BenchmarkVersionDto,
): BenchmarkVersion {
  return {
    id: dto.id,
    dataset_id: dto.dataset_id,
    version_number: dto.version_number,
    status: dto.status,
    threshold_profile_snapshot: benchmarkThresholdProfileApiToView(
      dto.threshold_profile_snapshot,
    ),
    case_count: dto.case_count ?? 0,
    content_hash: dto.content_hash ?? null,
    locked_by: dto.locked_by ?? null,
    locked_at: dto.locked_at ?? null,
    created_by: dto.created_by ?? null,
    created_at: dto.created_at ?? new Date().toISOString(),
    updated_at: dto.updated_at ?? new Date().toISOString(),
  };
}

export function benchmarkVersionListApiToView(
  dto: B15BenchmarkVersionListDto,
): BenchmarkVersionList {
  return { items: (dto.items ?? []).map(benchmarkVersionApiToView) };
}

export function benchmarkCaseApiToView(dto: B15BenchmarkCaseDto): BenchmarkCase {
  return {
    id: dto.id,
    dataset_version_id: dto.dataset_version_id,
    published_result_id: dto.published_result_id,
    evaluation_run_id: dto.evaluation_run_id,
    question_evaluation_id: dto.question_evaluation_id,
    question_version_id: dto.question_version_id,
    rubric_version_id: dto.rubric_version_id,
    assessment_version_id: dto.assessment_version_id,
    expected_final_marks: asNumberRequired(dto.expected_final_marks),
    expected_max_marks: asNumberRequired(dto.expected_max_marks),
    expected_error_codes: [...(dto.expected_error_codes ?? [])],
    source_ledger_hash: dto.source_ledger_hash,
    evidence_hash: dto.evidence_hash,
    adjudicated_by: dto.adjudicated_by ?? null,
    adjudicated_at: dto.adjudicated_at ?? new Date().toISOString(),
    replay_fixture: { ...(dto.replay_fixture ?? {}) },
    created_at: dto.created_at ?? new Date().toISOString(),
    updated_at: dto.updated_at ?? new Date().toISOString(),
  };
}

export function benchmarkCaseListApiToView(
  dto: B15BenchmarkCaseListDto,
): BenchmarkCaseList {
  return { items: (dto.items ?? []).map(benchmarkCaseApiToView) };
}

export function benchmarkEligibleSourcesApiToView(
  dto: B15EligibleSourcesDto,
): BenchmarkEligibleSources {
  return {
    items: (dto.items ?? []).map((item) => ({
      published_result_id: item.published_result_id,
      evaluation_run_id: item.evaluation_run_id,
      submission_id: item.submission_id,
      assessment_version_id: item.assessment_version_id,
      ledger_snapshot_hash: item.ledger_snapshot_hash,
      question_evaluations: (item.question_evaluations ?? []).map((qe) => ({
        question_evaluation_id: qe.question_evaluation_id,
        question_version_id: qe.question_version_id,
        workflow_state: qe.workflow_state,
        final_human_approved_score: asNumberRequired(
          qe.final_human_approved_score,
        ),
        max_mark: asNumberRequired(qe.max_mark),
        error_codes: [...(qe.error_codes ?? [])],
      })),
    })),
  };
}

export function benchmarkRegressionRunApiToView(
  dto: B15BenchmarkRegressionRunDto,
): BenchmarkRegressionRun {
  return {
    id: dto.id,
    dataset_version_id: dto.dataset_version_id,
    status: dto.status,
    verdict: dto.verdict,
    idempotency_key: dto.idempotency_key ?? null,
    candidate_provider: dto.candidate_provider,
    candidate_model: dto.candidate_model,
    candidate_model_version: dto.candidate_model_version,
    candidate_prompt_template_version: dto.candidate_prompt_template_version,
    candidate_config: { ...(dto.candidate_config ?? {}) },
    threshold_snapshot: benchmarkThresholdProfileApiToView(
      dto.threshold_snapshot,
    ),
    aggregate_metrics: { ...(dto.aggregate_metrics ?? {}) },
    initiated_by: dto.initiated_by ?? null,
    started_at: dto.started_at ?? null,
    finished_at: dto.finished_at ?? null,
    failure_code: dto.failure_code ?? null,
    failure_detail: dto.failure_detail ?? null,
    created_at: dto.created_at ?? new Date().toISOString(),
    updated_at: dto.updated_at ?? new Date().toISOString(),
  };
}

export function benchmarkRegressionRunListApiToView(
  dto: B15BenchmarkRegressionRunListDto,
): BenchmarkRegressionRunList {
  return { items: (dto.items ?? []).map(benchmarkRegressionRunApiToView) };
}

export function benchmarkRegressionCaseResultApiToView(
  dto: B15BenchmarkRegressionCaseResultDto,
): BenchmarkRegressionCaseResult {
  return {
    id: dto.id,
    regression_run_id: dto.regression_run_id,
    benchmark_case_id: dto.benchmark_case_id,
    missing_output: dto.missing_output,
    actual_marks: asNumber(dto.actual_marks),
    actual_error_codes: [...(dto.actual_error_codes ?? [])],
    score_abs_error: asNumber(dto.score_abs_error),
    exact_score_match: dto.exact_score_match,
    taxonomy_match:
      dto.taxonomy_match === undefined ? null : dto.taxonomy_match,
    safety_invariant_failed: dto.safety_invariant_failed,
    diff: { ...(dto.diff ?? {}) },
    ai_execution_record_id: dto.ai_execution_record_id ?? null,
    created_at: dto.created_at ?? new Date().toISOString(),
    updated_at: dto.updated_at ?? new Date().toISOString(),
  };
}

export function benchmarkRegressionCaseResultListApiToView(
  dto: B15BenchmarkRegressionCaseResultListDto,
): BenchmarkRegressionCaseResultList {
  return {
    items: (dto.items ?? []).map(benchmarkRegressionCaseResultApiToView),
  };
}

export function benchmarkGateVerdictApiToView(
  dto: B15BenchmarkGateVerdictDto,
): BenchmarkGateVerdict {
  return {
    verdict: dto.verdict,
    passed: dto.passed,
    run_id: dto.run_id,
    status: dto.status,
    candidate_provider: dto.candidate_provider,
    candidate_model: dto.candidate_model,
    candidate_model_version: dto.candidate_model_version,
    candidate_prompt_template_version: dto.candidate_prompt_template_version,
    metrics: { ...(dto.metrics ?? {}) },
    threshold_snapshot: benchmarkThresholdProfileApiToView(
      dto.threshold_snapshot,
    ),
  };
}

/**
 * Live B15 gold benchmark + isolated AI regression HTTP adapter.
 */
export const BenchmarkHttpApi = {
  async listBenchmarkDatasets(): Promise<BenchmarkDatasetList> {
    const dto = await httpRequest<B15BenchmarkDatasetListDto>(
      `/api/v1/quality/benchmark-datasets`,
    );
    return benchmarkDatasetListApiToView(dto);
  },

  async getBenchmarkDataset(id: string): Promise<BenchmarkDataset> {
    const dto = await httpRequest<B15BenchmarkDatasetDto>(
      `/api/v1/quality/benchmark-datasets/${id}`,
    );
    return benchmarkDatasetApiToView(dto);
  },

  async createBenchmarkDataset(
    input: BenchmarkDatasetCreate,
  ): Promise<BenchmarkDataset> {
    const dto = await httpRequest<B15BenchmarkDatasetDto>(
      `/api/v1/quality/benchmark-datasets`,
      {
        method: "POST",
        body: {
          code: input.code,
          title: input.title,
          description: input.description ?? null,
        },
      },
    );
    return benchmarkDatasetApiToView(dto);
  },

  async listBenchmarkVersions(
    datasetId: string,
  ): Promise<BenchmarkVersionList> {
    const dto = await httpRequest<B15BenchmarkVersionListDto>(
      `/api/v1/quality/benchmark-datasets/${datasetId}/versions`,
    );
    return benchmarkVersionListApiToView(dto);
  },

  async createBenchmarkVersion(
    datasetId: string,
    input?: BenchmarkVersionCreate,
  ): Promise<BenchmarkVersion> {
    const dto = await httpRequest<B15BenchmarkVersionDto>(
      `/api/v1/quality/benchmark-datasets/${datasetId}/versions`,
      {
        method: "POST",
        body: {
          threshold_profile_snapshot:
            input?.threshold_profile_snapshot ?? null,
        },
      },
    );
    return benchmarkVersionApiToView(dto);
  },

  async getBenchmarkVersion(versionId: string): Promise<BenchmarkVersion> {
    const dto = await httpRequest<B15BenchmarkVersionDto>(
      `/api/v1/quality/benchmark-versions/${versionId}`,
    );
    return benchmarkVersionApiToView(dto);
  },

  async listBenchmarkEligibleSources(
    versionId: string,
  ): Promise<BenchmarkEligibleSources> {
    const dto = await httpRequest<B15EligibleSourcesDto>(
      `/api/v1/quality/benchmark-versions/${versionId}/eligible-sources`,
    );
    return benchmarkEligibleSourcesApiToView(dto);
  },

  async listBenchmarkCases(versionId: string): Promise<BenchmarkCaseList> {
    const dto = await httpRequest<B15BenchmarkCaseListDto>(
      `/api/v1/quality/benchmark-versions/${versionId}/cases`,
    );
    return benchmarkCaseListApiToView(dto);
  },

  async addBenchmarkCase(
    versionId: string,
    input: BenchmarkCaseCreate,
  ): Promise<BenchmarkCase> {
    const dto = await httpRequest<B15BenchmarkCaseDto>(
      `/api/v1/quality/benchmark-versions/${versionId}/cases`,
      {
        method: "POST",
        body: {
          published_result_id: input.published_result_id,
          question_evaluation_id: input.question_evaluation_id,
        },
      },
    );
    return benchmarkCaseApiToView(dto);
  },

  async removeBenchmarkCase(
    versionId: string,
    caseId: string,
  ): Promise<BenchmarkCase> {
    const dto = await httpRequest<B15BenchmarkCaseDto>(
      `/api/v1/quality/benchmark-versions/${versionId}/cases/${caseId}`,
      { method: "DELETE" },
    );
    return benchmarkCaseApiToView(dto);
  },

  async lockBenchmarkVersion(versionId: string): Promise<BenchmarkVersion> {
    const dto = await httpRequest<B15BenchmarkVersionDto>(
      `/api/v1/quality/benchmark-versions/${versionId}/lock`,
      { method: "POST" },
    );
    return benchmarkVersionApiToView(dto);
  },

  async listBenchmarkRegressionRuns(
    versionId: string,
  ): Promise<BenchmarkRegressionRunList> {
    const dto = await httpRequest<B15BenchmarkRegressionRunListDto>(
      `/api/v1/quality/benchmark-versions/${versionId}/regression-runs`,
    );
    return benchmarkRegressionRunListApiToView(dto);
  },

  async startBenchmarkRegressionRun(
    versionId: string,
    input: BenchmarkRegressionRunCreate,
  ): Promise<BenchmarkRegressionRun> {
    const dto = await httpRequest<B15BenchmarkRegressionRunDto>(
      `/api/v1/quality/benchmark-versions/${versionId}/regression-runs`,
      {
        method: "POST",
        body: {
          candidate_provider: input.candidate_provider,
          candidate_model: input.candidate_model,
          candidate_model_version: input.candidate_model_version,
          candidate_prompt_template_version:
            input.candidate_prompt_template_version,
          candidate_config: input.candidate_config ?? null,
          idempotency_key: input.idempotency_key ?? null,
        },
      },
    );
    return benchmarkRegressionRunApiToView(dto);
  },

  async getBenchmarkRegressionRun(
    runId: string,
  ): Promise<BenchmarkRegressionRun> {
    const dto = await httpRequest<B15BenchmarkRegressionRunDto>(
      `/api/v1/quality/regression-runs/${runId}`,
    );
    return benchmarkRegressionRunApiToView(dto);
  },

  async listBenchmarkRegressionCaseResults(
    runId: string,
  ): Promise<BenchmarkRegressionCaseResultList> {
    const dto = await httpRequest<B15BenchmarkRegressionCaseResultListDto>(
      `/api/v1/quality/regression-runs/${runId}/case-results`,
    );
    return benchmarkRegressionCaseResultListApiToView(dto);
  },

  async getBenchmarkGateVerdict(runId: string): Promise<BenchmarkGateVerdict> {
    const dto = await httpRequest<B15BenchmarkGateVerdictDto>(
      `/api/v1/quality/regression-runs/${runId}/gate`,
    );
    return benchmarkGateVerdictApiToView(dto);
  },
};
