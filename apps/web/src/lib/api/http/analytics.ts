import type {
  AnalyticsMaterializationPrepareResult,
  LiveAssessmentAnalytics,
  LiveConceptSignal,
  LiveCurriculumPerformance,
  LiveQuestionPerformance,
  LiveStudentAnalytics,
  MasteryEvidenceItem,
  StudentMasteryEvidenceList,
} from "@/lib/types/domain";
import type { ErrorCode } from "@/lib/types/enums";
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

export interface B8AssessmentAnalyticsDto {
  assessment: {
    id: string;
    code: string;
    title: string;
    curriculum_id: string;
    status: string;
  };
  class_section_id?: string | null;
  published_attempt_count: number;
  unique_student_count: number;
  mean_percentage: number | string | null;
  median_percentage: number | string | null;
  pass_threshold_percent: number | string | null;
  pass_rate: number | string | null;
  score_distribution: Array<{
    lower_bound: number | string;
    upper_bound: number | string;
    count: number;
  }>;
  question_performance: Array<{
    question_id: string;
    question_code: string;
    question_version_ids?: string[];
    attempt_count: number;
    blank_count: number;
    mean_score_percent: number | string | null;
    median_score_percent: number | string | null;
    full_credit_count: number;
    zero_score_count: number;
    common_errors?: Array<{ code: string; count: number; category?: string }>;
  }>;
  error_distribution: {
    academic?: Array<{ code: string; count: number; category?: string }>;
    review_conditions?: Array<{
      code: string;
      count: number;
      category?: string;
    }>;
  };
  curriculum_performance?: Array<{
    curriculum_node_id: string;
    code: string;
    title: string;
    node_type: string;
    question_count: number;
    evidence_count: number;
    mean_score_ratio: number | string | null;
    strong_signal_count: number;
    weak_signal_count: number;
    inconclusive_signal_count: number;
    common_academic_errors?: Array<{ code: string; count: number }>;
  }>;
  mapped_scorable_question_count?: number;
  unmapped_scorable_question_count?: number;
  mastery_coverage_ratio: number | string | null;
  source?: string;
  as_of?: string;
}

export interface B8StudentAnalyticsDto {
  student: {
    id: string;
    display_name: string;
    student_code?: string | null;
    external_ref?: string | null;
  };
  published_assessment_count: number;
  published_attempt_count: number;
  average_percentage: number | string | null;
  concept_signals?: Array<{
    curriculum_node_id: string;
    code: string;
    title: string;
    node_type: string;
    concept: {
      strong_count: number;
      weak_count: number;
      inconclusive_count: number;
      signal: string;
    };
    execution: {
      strong_count: number;
      weak_count: number;
      inconclusive_count: number;
      signal: string;
    };
    procedure: {
      strong_count: number;
      weak_count: number;
      inconclusive_count: number;
      signal: string;
    };
    evidence_count: number;
    mean_score_ratio: number | string | null;
  }>;
  error_distribution?: Array<{ code: string; count: number }>;
  mastery_coverage?: {
    curriculum_node_count: number;
    evidence_row_count: number;
  };
  materialization_status: string;
  published_result_count: number;
  materialized_result_count: number;
  source?: string;
  as_of?: string;
}

export interface B8MasteryEvidenceListDto {
  student_id: string;
  items: Array<{
    id: string;
    published_result_id: string;
    assessment_id: string;
    assessment_version_id: string;
    submission_id: string;
    evaluation_run_id: string;
    question_evaluation_id: string;
    question_version_id: string;
    curriculum_id: string;
    curriculum_node_id: string;
    evidence_type: string;
    strength: string;
    score_ratio: number | string;
    source_final_score: number | string;
    source_max_mark: number | string;
    mapping_types?: string[];
    mapping_weight?: number | string | null;
    academic_error_codes?: string[];
    review_condition_codes?: string[];
    reason_codes?: string[];
    source_ledger_snapshot_hash: string;
    algorithm_version: string;
    created_at: string;
  }>;
}

function mapErrorCount(item: {
  code: string;
  count: number;
  category?: string;
}): { code: ErrorCode | string; count: number; category?: string } {
  return {
    code: item.code,
    count: item.count,
    category: item.category,
  };
}

function mapQuestionPerformance(
  row: B8AssessmentAnalyticsDto["question_performance"][number],
): LiveQuestionPerformance {
  return {
    question_id: row.question_id,
    question_code: row.question_code,
    question_version_ids: row.question_version_ids ?? [],
    attempt_count: row.attempt_count,
    blank_count: row.blank_count,
    mean_score_percent: asNumber(row.mean_score_percent),
    median_score_percent: asNumber(row.median_score_percent),
    full_credit_count: row.full_credit_count,
    zero_score_count: row.zero_score_count,
    common_errors: (row.common_errors ?? []).map(mapErrorCount),
  };
}

function mapCurriculumPerformance(
  row: NonNullable<B8AssessmentAnalyticsDto["curriculum_performance"]>[number],
): LiveCurriculumPerformance {
  return {
    curriculum_node_id: row.curriculum_node_id,
    code: row.code,
    title: row.title,
    node_type: row.node_type,
    question_count: row.question_count,
    evidence_count: row.evidence_count,
    mean_score_ratio: asNumber(row.mean_score_ratio),
    strong_signal_count: row.strong_signal_count,
    weak_signal_count: row.weak_signal_count,
    inconclusive_signal_count: row.inconclusive_signal_count,
    common_academic_errors: (row.common_academic_errors ?? []).map(
      mapErrorCount,
    ),
  };
}

export function assessmentAnalyticsApiToView(
  dto: B8AssessmentAnalyticsDto,
): LiveAssessmentAnalytics {
  return {
    assessment: {
      id: dto.assessment.id,
      code: dto.assessment.code,
      title: dto.assessment.title,
      curriculum_id: dto.assessment.curriculum_id,
      status: dto.assessment.status,
    },
    class_section_id: dto.class_section_id ?? null,
    published_attempt_count: asNumberRequired(dto.published_attempt_count),
    unique_student_count: asNumberRequired(dto.unique_student_count),
    mean_percentage: asNumber(dto.mean_percentage),
    median_percentage: asNumber(dto.median_percentage),
    pass_threshold_percent: asNumber(dto.pass_threshold_percent),
    pass_rate: asNumber(dto.pass_rate),
    score_distribution: (dto.score_distribution ?? []).map((band) => ({
      lower_bound: asNumberRequired(band.lower_bound),
      upper_bound: asNumberRequired(band.upper_bound),
      count: band.count,
    })),
    question_performance: (dto.question_performance ?? []).map(
      mapQuestionPerformance,
    ),
    error_distribution: {
      academic: (dto.error_distribution?.academic ?? []).map(mapErrorCount),
      review_conditions: (
        dto.error_distribution?.review_conditions ?? []
      ).map(mapErrorCount),
    },
    curriculum_performance: (dto.curriculum_performance ?? []).map(
      mapCurriculumPerformance,
    ),
    mapped_scorable_question_count: asNumberRequired(
      dto.mapped_scorable_question_count,
    ),
    unmapped_scorable_question_count: asNumberRequired(
      dto.unmapped_scorable_question_count,
    ),
    mastery_coverage_ratio: asNumber(dto.mastery_coverage_ratio),
    source: "PUBLISHED_LEDGER",
    as_of: dto.as_of ?? new Date().toISOString(),
  };
}

function mapConceptSignal(
  row: NonNullable<B8StudentAnalyticsDto["concept_signals"]>[number],
): LiveConceptSignal {
  return {
    curriculum_node_id: row.curriculum_node_id,
    code: row.code,
    title: row.title,
    node_type: row.node_type,
    concept: row.concept,
    execution: row.execution,
    procedure: row.procedure,
    evidence_count: row.evidence_count,
    mean_score_ratio: asNumber(row.mean_score_ratio),
  };
}

export function studentAnalyticsApiToView(
  dto: B8StudentAnalyticsDto,
): LiveStudentAnalytics {
  return {
    student: {
      id: dto.student.id,
      display_name: dto.student.display_name,
      student_code: dto.student.student_code ?? null,
      external_ref: dto.student.external_ref ?? null,
    },
    published_assessment_count: asNumberRequired(
      dto.published_assessment_count,
    ),
    published_attempt_count: asNumberRequired(dto.published_attempt_count),
    average_percentage: asNumber(dto.average_percentage),
    concept_signals: (dto.concept_signals ?? []).map(mapConceptSignal),
    error_distribution: (dto.error_distribution ?? []).map(mapErrorCount),
    mastery_coverage: {
      curriculum_node_count:
        dto.mastery_coverage?.curriculum_node_count ?? 0,
      evidence_row_count: dto.mastery_coverage?.evidence_row_count ?? 0,
    },
    materialization_status: dto.materialization_status,
    published_result_count: asNumberRequired(dto.published_result_count),
    materialized_result_count: asNumberRequired(
      dto.materialized_result_count,
    ),
    source: "PUBLISHED_LEDGER",
    as_of: dto.as_of ?? new Date().toISOString(),
  };
}

function masteryEvidenceApiToView(
  row: B8MasteryEvidenceListDto["items"][number],
): MasteryEvidenceItem {
  return {
    id: row.id,
    published_result_id: row.published_result_id,
    assessment_id: row.assessment_id,
    assessment_version_id: row.assessment_version_id,
    submission_id: row.submission_id,
    evaluation_run_id: row.evaluation_run_id,
    question_evaluation_id: row.question_evaluation_id,
    question_version_id: row.question_version_id,
    curriculum_id: row.curriculum_id,
    curriculum_node_id: row.curriculum_node_id,
    evidence_type: row.evidence_type,
    strength: row.strength,
    score_ratio: asNumberRequired(row.score_ratio),
    source_final_score: asNumberRequired(row.source_final_score),
    source_max_mark: asNumberRequired(row.source_max_mark),
    mapping_types: row.mapping_types ?? [],
    mapping_weight: asNumber(row.mapping_weight),
    academic_error_codes: row.academic_error_codes ?? [],
    review_condition_codes: row.review_condition_codes ?? [],
    reason_codes: row.reason_codes ?? [],
    source_ledger_snapshot_hash: row.source_ledger_snapshot_hash,
    algorithm_version: row.algorithm_version,
    created_at: row.created_at,
  };
}

/**
 * Live B8 analytics / mastery-evidence HTTP adapter.
 */
export const AnalyticsHttpApi = {
  async getAssessmentAnalytics(
    assessmentId: string,
    options?: { passThresholdPercent?: number },
  ): Promise<LiveAssessmentAnalytics> {
    const params = new URLSearchParams();
    if (
      options?.passThresholdPercent !== undefined &&
      options.passThresholdPercent !== null &&
      Number.isFinite(options.passThresholdPercent)
    ) {
      params.set(
        "pass_threshold_percent",
        String(options.passThresholdPercent),
      );
    }
    const qs = params.toString();
    const path = `/api/v1/analytics/assessments/${assessmentId}${
      qs ? `?${qs}` : ""
    }`;
    const dto = await httpRequest<B8AssessmentAnalyticsDto>(path);
    return assessmentAnalyticsApiToView(dto);
  },

  async getStudentAnalytics(studentId: string): Promise<LiveStudentAnalytics> {
    const dto = await httpRequest<B8StudentAnalyticsDto>(
      `/api/v1/analytics/students/${studentId}`,
    );
    return studentAnalyticsApiToView(dto);
  },

  async getStudentMasteryEvidence(
    studentId: string,
    filters?: {
      assessmentId?: string;
      curriculumId?: string;
      curriculumNodeId?: string;
    },
  ): Promise<StudentMasteryEvidenceList> {
    const params = new URLSearchParams();
    if (filters?.assessmentId) {
      params.set("assessment_id", filters.assessmentId);
    }
    if (filters?.curriculumId) {
      params.set("curriculum_id", filters.curriculumId);
    }
    if (filters?.curriculumNodeId) {
      params.set("curriculum_node_id", filters.curriculumNodeId);
    }
    const qs = params.toString();
    const path = `/api/v1/analytics/students/${studentId}/mastery-evidence${
      qs ? `?${qs}` : ""
    }`;
    const dto = await httpRequest<B8MasteryEvidenceListDto>(path);
    return {
      student_id: dto.student_id,
      items: (dto.items ?? []).map(masteryEvidenceApiToView),
    };
  },

  async prepareAnalyticsMaterialization(
    publishedResultId: string,
  ): Promise<AnalyticsMaterializationPrepareResult> {
    const dto = await httpRequest<{
      published_result_id: string;
      pipeline_job_id: string;
      job_status: string;
      celery_task_id?: string | null;
      enqueue_error?: string | null;
      algorithm_version?: string;
    }>(`/api/v1/analytics/published-results/${publishedResultId}/prepare`, {
      method: "POST",
    });
    return {
      published_result_id: dto.published_result_id,
      pipeline_job_id: dto.pipeline_job_id,
      job_status: dto.job_status,
      celery_task_id: dto.celery_task_id ?? null,
      enqueue_error: dto.enqueue_error ?? null,
      algorithm_version: dto.algorithm_version ?? "B8_V1",
    };
  },
};
