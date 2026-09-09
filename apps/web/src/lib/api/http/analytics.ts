import type {
  AnalyticsMaterializationPrepareResult,
  B12RebuildResult,
  LiveAssessmentAnalytics,
  LiveConceptSignal,
  LiveCurriculumPerformance,
  LiveQuestionPerformance,
  LiveStudentAnalytics,
  MasteryEvidenceItem,
  MasteryStateItem,
  MasteryTrendPoint,
  MistakeNotebookEntry,
  RecoverableMarksItem,
  RepeatedErrorItem,
  StudentMasteryEvidenceList,
  StudentMasteryState,
  StudentMasteryTrend,
  StudentMistakeNotebook,
  StudentRecoverableMarks,
  StudentRepeatedErrors,
} from "@/lib/types/domain";
import {
  B12_RECOVERABLE_MARKS_DISCLAIMER,
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

export interface B12MasteryStateDto {
  student_id: string;
  items?: Array<{
    id?: string | null;
    curriculum_node_id: string;
    curriculum_id: string;
    code: string;
    title: string;
    node_type: string;
    concept_mastery: number | string | null;
    execution_accuracy: number | string | null;
    concept_decisive_count: number | string;
    execution_decisive_count: number | string;
    concept_inconclusive_count: number | string;
    execution_inconclusive_count: number | string;
    evidence_count: number | string;
    insufficient_concept_evidence: boolean;
    insufficient_execution_evidence: boolean;
    source_evidence_hash: string;
    algorithm_version?: string;
    last_updated_at: string;
  }>;
  algorithm_version?: string;
  source?: string;
  as_of?: string;
}

export interface B12MasteryTrendDto {
  student_id: string;
  curriculum_node_id?: string | null;
  points?: Array<{
    curriculum_node_id: string;
    curriculum_id: string;
    code: string;
    title: string;
    published_result_id: string;
    assessment_id: string;
    assessment_code: string;
    effective_at: string;
    concept_mastery: number | string | null;
    execution_accuracy: number | string | null;
    concept_decisive_count: number | string;
    execution_decisive_count: number | string;
    evidence_count: number | string;
    insufficient_concept_evidence: boolean;
    insufficient_execution_evidence: boolean;
    source_evidence_hash: string;
    algorithm_version?: string;
  }>;
  algorithm_version?: string;
  source?: string;
  as_of?: string;
}

export interface B12RepeatedErrorsDto {
  student_id: string;
  items?: Array<{
    error_code: string;
    occurrence_count: number | string;
    distinct_published_result_count: number | string;
    distinct_assessment_count: number | string;
    first_seen_at: string;
    last_seen_at: string;
    affected_question_evaluations?: Array<{
      published_result_id: string;
      assessment_id: string;
      question_evaluation_id: string;
      question_version_id: string;
    }>;
    curriculum_node_ids?: string[];
  }>;
  recurrence_threshold?: number;
  algorithm_version?: string;
  source?: string;
  as_of?: string;
}

export interface B12RecoverableMarksDto {
  student_id: string;
  total_lost_marks: string | number;
  attributed_potentially_recoverable_marks: string | number;
  unattributed_lost_marks: string | number;
  items?: Array<{
    error_code: string;
    potentially_recoverable_marks: string | number;
    occurrence_count: number | string;
    percent_of_total_lost: number | string | null;
    affected_references?: Array<{
      published_result_id: string;
      assessment_id: string;
      question_evaluation_id: string;
      criterion_evaluation_id: string;
    }>;
  }>;
  disclaimer?: string;
  algorithm_version?: string;
  source?: string;
  as_of?: string;
}

export interface B12MistakeNotebookDto {
  student_id: string;
  entries?: Array<{
    id: string;
    published_result_id: string;
    assessment_id: string;
    assessment_code: string;
    submission_id: string;
    question_evaluation_id: string;
    question_version_id: string;
    question_code: string;
    academic_error_code: string;
    final_score: string | number;
    max_mark: string | number;
    deduction_reasons?: string[];
    first_divergence_step?: string | null;
    curriculum_nodes?: Array<{
      id: string;
      code: string;
      title: string;
      node_type: string;
    }>;
    recommended_practice_kind: string;
    linked_learning_recommendation_ids?: string[];
    source_ledger_snapshot_hash: string;
    algorithm_version?: string;
    materialized_at: string;
    effective_at: string;
  }>;
  algorithm_version?: string;
  source?: string;
  as_of?: string;
}

export interface B12RebuildResultDto {
  student_id: string;
  algorithm_version?: string;
  mastery_state_count: number | string;
  snapshot_count: number | string;
  notebook_entry_count: number | string;
  source_evidence_hash: string;
  source?: string;
}

function asDecimalString(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "0";
  return String(value);
}

function mapMasteryStateItem(
  row: NonNullable<B12MasteryStateDto["items"]>[number],
): MasteryStateItem {
  return {
    id: row.id ?? null,
    curriculum_node_id: row.curriculum_node_id,
    curriculum_id: row.curriculum_id,
    code: row.code,
    title: row.title,
    node_type: row.node_type,
    concept_mastery: asNumber(row.concept_mastery),
    execution_accuracy: asNumber(row.execution_accuracy),
    concept_decisive_count: asNumberRequired(row.concept_decisive_count),
    execution_decisive_count: asNumberRequired(row.execution_decisive_count),
    concept_inconclusive_count: asNumberRequired(row.concept_inconclusive_count),
    execution_inconclusive_count: asNumberRequired(
      row.execution_inconclusive_count,
    ),
    evidence_count: asNumberRequired(row.evidence_count),
    insufficient_concept_evidence: Boolean(row.insufficient_concept_evidence),
    insufficient_execution_evidence: Boolean(
      row.insufficient_execution_evidence,
    ),
    source_evidence_hash: row.source_evidence_hash,
    algorithm_version: row.algorithm_version ?? "B12_V1",
    last_updated_at: row.last_updated_at,
  };
}

export function masteryStateApiToView(
  dto: B12MasteryStateDto,
): StudentMasteryState {
  return {
    student_id: dto.student_id,
    items: (dto.items ?? []).map(mapMasteryStateItem),
    algorithm_version: dto.algorithm_version ?? "B12_V1",
    source: "MASTERY_EVIDENCE",
    as_of: dto.as_of ?? new Date().toISOString(),
  };
}

function mapMasteryTrendPoint(
  row: NonNullable<B12MasteryTrendDto["points"]>[number],
): MasteryTrendPoint {
  return {
    curriculum_node_id: row.curriculum_node_id,
    curriculum_id: row.curriculum_id,
    code: row.code,
    title: row.title,
    published_result_id: row.published_result_id,
    assessment_id: row.assessment_id,
    assessment_code: row.assessment_code,
    effective_at: row.effective_at,
    concept_mastery: asNumber(row.concept_mastery),
    execution_accuracy: asNumber(row.execution_accuracy),
    concept_decisive_count: asNumberRequired(row.concept_decisive_count),
    execution_decisive_count: asNumberRequired(row.execution_decisive_count),
    evidence_count: asNumberRequired(row.evidence_count),
    insufficient_concept_evidence: Boolean(row.insufficient_concept_evidence),
    insufficient_execution_evidence: Boolean(
      row.insufficient_execution_evidence,
    ),
    source_evidence_hash: row.source_evidence_hash,
    algorithm_version: row.algorithm_version ?? "B12_V1",
  };
}

export function masteryTrendApiToView(
  dto: B12MasteryTrendDto,
): StudentMasteryTrend {
  return {
    student_id: dto.student_id,
    curriculum_node_id: dto.curriculum_node_id ?? null,
    points: (dto.points ?? []).map(mapMasteryTrendPoint),
    algorithm_version: dto.algorithm_version ?? "B12_V1",
    source: "MASTERY_EVIDENCE",
    as_of: dto.as_of ?? new Date().toISOString(),
  };
}

function mapRepeatedErrorItem(
  row: NonNullable<B12RepeatedErrorsDto["items"]>[number],
): RepeatedErrorItem {
  return {
    error_code: row.error_code,
    occurrence_count: asNumberRequired(row.occurrence_count),
    distinct_published_result_count: asNumberRequired(
      row.distinct_published_result_count,
    ),
    distinct_assessment_count: asNumberRequired(row.distinct_assessment_count),
    first_seen_at: row.first_seen_at,
    last_seen_at: row.last_seen_at,
    affected_question_evaluations: (
      row.affected_question_evaluations ?? []
    ).map((ref) => ({
      published_result_id: ref.published_result_id,
      assessment_id: ref.assessment_id,
      question_evaluation_id: ref.question_evaluation_id,
      question_version_id: ref.question_version_id,
    })),
    curriculum_node_ids: row.curriculum_node_ids ?? [],
  };
}

export function repeatedErrorsApiToView(
  dto: B12RepeatedErrorsDto,
): StudentRepeatedErrors {
  return {
    student_id: dto.student_id,
    items: (dto.items ?? []).map(mapRepeatedErrorItem),
    recurrence_threshold: asNumberRequired(dto.recurrence_threshold, 2),
    algorithm_version: dto.algorithm_version ?? "B12_V1",
    source: "MASTERY_EVIDENCE",
    as_of: dto.as_of ?? new Date().toISOString(),
  };
}

function mapRecoverableMarksItem(
  row: NonNullable<B12RecoverableMarksDto["items"]>[number],
): RecoverableMarksItem {
  return {
    error_code: row.error_code,
    potentially_recoverable_marks: asDecimalString(
      row.potentially_recoverable_marks,
    ),
    occurrence_count: asNumberRequired(row.occurrence_count),
    percent_of_total_lost: asNumber(row.percent_of_total_lost),
    affected_references: (row.affected_references ?? []).map((ref) => ({
      published_result_id: ref.published_result_id,
      assessment_id: ref.assessment_id,
      question_evaluation_id: ref.question_evaluation_id,
      criterion_evaluation_id: ref.criterion_evaluation_id,
    })),
  };
}

export function recoverableMarksApiToView(
  dto: B12RecoverableMarksDto,
): StudentRecoverableMarks {
  return {
    student_id: dto.student_id,
    total_lost_marks: asDecimalString(dto.total_lost_marks),
    attributed_potentially_recoverable_marks: asDecimalString(
      dto.attributed_potentially_recoverable_marks,
    ),
    unattributed_lost_marks: asDecimalString(dto.unattributed_lost_marks),
    items: (dto.items ?? []).map(mapRecoverableMarksItem),
    disclaimer: dto.disclaimer ?? B12_RECOVERABLE_MARKS_DISCLAIMER,
    algorithm_version: dto.algorithm_version ?? "B12_V1",
    source: "PUBLISHED_LEDGER",
    as_of: dto.as_of ?? new Date().toISOString(),
  };
}

function mapMistakeNotebookEntry(
  row: NonNullable<B12MistakeNotebookDto["entries"]>[number],
): MistakeNotebookEntry {
  return {
    id: row.id,
    published_result_id: row.published_result_id,
    assessment_id: row.assessment_id,
    assessment_code: row.assessment_code,
    submission_id: row.submission_id,
    question_evaluation_id: row.question_evaluation_id,
    question_version_id: row.question_version_id,
    question_code: row.question_code,
    academic_error_code: row.academic_error_code,
    final_score: asDecimalString(row.final_score),
    max_mark: asDecimalString(row.max_mark),
    deduction_reasons: row.deduction_reasons ?? [],
    first_divergence_step: row.first_divergence_step ?? null,
    curriculum_nodes: (row.curriculum_nodes ?? []).map((n) => ({
      id: n.id,
      code: n.code,
      title: n.title,
      node_type: n.node_type,
    })),
    recommended_practice_kind: row.recommended_practice_kind,
    linked_learning_recommendation_ids:
      row.linked_learning_recommendation_ids ?? [],
    source_ledger_snapshot_hash: row.source_ledger_snapshot_hash,
    algorithm_version: row.algorithm_version ?? "B12_V1",
    materialized_at: row.materialized_at,
    effective_at: row.effective_at,
  };
}

export function mistakeNotebookApiToView(
  dto: B12MistakeNotebookDto,
): StudentMistakeNotebook {
  return {
    student_id: dto.student_id,
    entries: (dto.entries ?? []).map(mapMistakeNotebookEntry),
    algorithm_version: dto.algorithm_version ?? "B12_V1",
    source: "PUBLISHED_LEDGER",
    as_of: dto.as_of ?? new Date().toISOString(),
  };
}

export function b12RebuildApiToView(dto: B12RebuildResultDto): B12RebuildResult {
  return {
    student_id: dto.student_id,
    algorithm_version: dto.algorithm_version ?? "B12_V1",
    mastery_state_count: asNumberRequired(dto.mastery_state_count),
    snapshot_count: asNumberRequired(dto.snapshot_count),
    notebook_entry_count: asNumberRequired(dto.notebook_entry_count),
    source_evidence_hash: dto.source_evidence_hash,
    source: "MASTERY_EVIDENCE",
  };
}

/**
 * Live B8 analytics / mastery-evidence + B12 longitudinal HTTP adapter.
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

  async getStudentMasteryState(
    studentId: string,
  ): Promise<StudentMasteryState> {
    const dto = await httpRequest<B12MasteryStateDto>(
      `/api/v1/analytics/students/${studentId}/mastery-state`,
    );
    return masteryStateApiToView(dto);
  },

  async getStudentMasteryTrend(
    studentId: string,
    options?: { curriculumNodeId?: string },
  ): Promise<StudentMasteryTrend> {
    const params = new URLSearchParams();
    if (options?.curriculumNodeId) {
      params.set("curriculum_node_id", options.curriculumNodeId);
    }
    const qs = params.toString();
    const path = `/api/v1/analytics/students/${studentId}/mastery-trend${
      qs ? `?${qs}` : ""
    }`;
    const dto = await httpRequest<B12MasteryTrendDto>(path);
    return masteryTrendApiToView(dto);
  },

  async getStudentRepeatedErrors(
    studentId: string,
  ): Promise<StudentRepeatedErrors> {
    const dto = await httpRequest<B12RepeatedErrorsDto>(
      `/api/v1/analytics/students/${studentId}/repeated-errors`,
    );
    return repeatedErrorsApiToView(dto);
  },

  async getStudentRecoverableMarks(
    studentId: string,
  ): Promise<StudentRecoverableMarks> {
    const dto = await httpRequest<B12RecoverableMarksDto>(
      `/api/v1/analytics/students/${studentId}/recoverable-marks`,
    );
    return recoverableMarksApiToView(dto);
  },

  async getStudentMistakeNotebook(
    studentId: string,
  ): Promise<StudentMistakeNotebook> {
    const dto = await httpRequest<B12MistakeNotebookDto>(
      `/api/v1/analytics/students/${studentId}/mistake-notebook`,
    );
    return mistakeNotebookApiToView(dto);
  },

  async rebuildStudentB12(studentId: string): Promise<B12RebuildResult> {
    const dto = await httpRequest<B12RebuildResultDto>(
      `/api/v1/analytics/students/${studentId}/b12/rebuild`,
      { method: "POST" },
    );
    return b12RebuildApiToView(dto);
  },
};
