import type {
  ImprovementBlueprintPrepareResult,
  LearningPlanPrepareResult,
  LiveImprovementAssessment,
  LiveImprovementAssessmentItem,
  LiveLearningCurriculumOption,
  LiveLearningPathStep,
  LiveLearningPlan,
  LiveLearningPlanRunSummary,
  LiveLearningPrerequisiteRef,
  LiveLearningRecommendation,
  LiveLearningWorkspace,
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

export interface B9LearningWorkspaceDto {
  student: {
    id: string;
    display_name: string;
    student_code?: string | null;
    external_ref?: string | null;
  };
  available_curricula?: Array<{
    id?: string;
    curriculum_id?: string;
    code: string;
    name: string;
  }>;
  selected_curriculum?: {
    id: string;
    code: string;
    name: string;
  } | null;
  selected_curriculum_id?: string | null;
  materialization_status: string;
  evidence_coverage?: {
    curriculum_node_count?: number;
    evidence_row_count?: number;
    node_count?: number;
    evidence_count?: number;
  };
  latest_run?: B9PlanRunDto | null;
  latest_plan?: B9LearningPlanDto | null;
  is_stale?: boolean;
  latest_improvement_blueprint?: B9ImprovementAssessmentDto | null;
}

export interface B9PlanRunDto {
  id: string;
  version_number: number;
  status: string;
  generation_source?: string | null;
  algorithm_version?: string;
  source_evidence_hash?: string;
  curriculum_graph_hash?: string;
  input_hash?: string;
  failure_code?: string | null;
  failure_detail?: string | null;
  requested_at?: string | null;
  finished_at?: string | null;
  student_id?: string;
  curriculum_id?: string;
  is_stale?: boolean;
  recommendations?: B9RecommendationDto[];
  path?: B9PathStepDto[];
  learning_path?: B9PathStepDto[];
  materialization_status?: string | null;
  evidence_coverage?: {
    curriculum_node_count?: number;
    evidence_row_count?: number;
  };
}

export interface B9RecommendationDto {
  id: string;
  curriculum_node_id: string;
  target_node_id?: string;
  code?: string;
  title?: string;
  node_type?: string;
  target_node_code?: string;
  target_node_title?: string;
  target_node_type?: string;
  target_node_code_snapshot?: string;
  target_node_title_snapshot?: string;
  target_node_type_snapshot?: string;
  recommendation_kind: string;
  priority: number;
  rationale?: string;
  concept_signal: string;
  execution_signal: string;
  procedure_signal: string;
  evidence_count?: number;
  mean_evidence_score_ratio?: number | string | null;
  status?: string;
  prerequisites?: Array<{
    curriculum_node_id: string;
    code?: string;
    title?: string;
    relationship_type: string;
  }>;
}

export interface B9PathStepDto {
  id: string;
  kind: string;
  sequence: number;
  title: string;
  description?: string;
  curriculum_node_id?: string | null;
  node_code?: string | null;
  node_title?: string | null;
  evidence_basis?: string | null;
  relationship_type?: string | null;
  estimated_minutes?: number | string | null;
  learning_recommendation_id?: string | null;
}

export interface B9LearningPlanDto {
  run_id?: string;
  id?: string;
  version_number: number;
  status: string;
  generation_source?: string | null;
  algorithm_version?: string;
  source_evidence_hash?: string;
  curriculum_graph_hash?: string;
  input_hash?: string;
  is_stale?: boolean;
  recommendations?: B9RecommendationDto[];
  path?: B9PathStepDto[];
  learning_path?: B9PathStepDto[];
  materialization_status?: string | null;
  evidence_coverage?: {
    curriculum_node_count?: number;
    evidence_row_count?: number;
  };
}

export interface B9ImprovementItemDto {
  id: string;
  learning_recommendation_id?: string | null;
  curriculum_node_id: string;
  node_code?: string | null;
  node_title?: string | null;
  item_code: string;
  template_kind: string;
  question_template_ref: string;
  focus: string;
  difficulty: string;
  suggested_marks?: number | string | null;
  sort_order: number;
}

export interface B9ImprovementAssessmentDto {
  id: string;
  student_id: string;
  curriculum_id: string;
  learning_plan_run_id: string;
  version_number: number;
  title: string;
  status: string;
  generation_source?: string | null;
  algorithm_version?: string | null;
  source_evidence_hash?: string | null;
  curriculum_graph_hash?: string | null;
  input_hash?: string | null;
  is_stale?: boolean;
  rejection_reason?: string | null;
  failure_code?: string | null;
  failure_detail?: string | null;
  items?: B9ImprovementItemDto[];
  generated_at?: string | null;
  approved_at?: string | null;
  rejected_at?: string | null;
  created_at?: string;
}

function mapCurriculum(
  row: {
    id?: string;
    curriculum_id?: string;
    code: string;
    name: string;
  },
): LiveLearningCurriculumOption {
  return {
    id: row.id ?? row.curriculum_id ?? "",
    code: row.code,
    name: row.name,
  };
}

function mapPrerequisite(
  row: NonNullable<B9RecommendationDto["prerequisites"]>[number],
): LiveLearningPrerequisiteRef {
  return {
    curriculum_node_id: row.curriculum_node_id,
    code: row.code ?? "",
    title: row.title ?? "",
    relationship_type:
      row.relationship_type === "RECOMMENDED" ? "RECOMMENDED" : "REQUIRED",
  };
}

function mapRecommendation(
  row: B9RecommendationDto,
): LiveLearningRecommendation {
  const priorityRaw = Number(row.priority);
  const priority =
    priorityRaw === 1 || priorityRaw === 2 || priorityRaw === 3
      ? priorityRaw
      : 3;
  return {
    id: row.id,
    curriculum_node_id: row.curriculum_node_id || row.target_node_id || "",
    code: row.code ?? row.target_node_code_snapshot ?? row.target_node_code ?? "",
    title:
      row.title ?? row.target_node_title_snapshot ?? row.target_node_title ?? "",
    node_type:
      row.node_type ?? row.target_node_type_snapshot ?? row.target_node_type ?? "",
    recommendation_kind: row.recommendation_kind,
    priority,
    rationale: row.rationale ?? "",
    concept_signal: row.concept_signal,
    execution_signal: row.execution_signal,
    procedure_signal: row.procedure_signal,
    evidence_count: asNumberRequired(row.evidence_count),
    mean_evidence_score_ratio: asNumber(row.mean_evidence_score_ratio),
    status: row.status ?? "ACTIVE",
    prerequisites: (row.prerequisites ?? []).map(mapPrerequisite),
  };
}

function mapPathStep(row: B9PathStepDto): LiveLearningPathStep {
  const rel = row.relationship_type;
  return {
    id: row.id,
    kind: row.kind,
    sequence: row.sequence,
    title: row.title,
    description: row.description ?? "",
    curriculum_node_id: row.curriculum_node_id ?? null,
    node_code: row.node_code ?? null,
    node_title: row.node_title ?? null,
    evidence_basis: row.evidence_basis ?? null,
    relationship_type:
      rel === "REQUIRED" || rel === "RECOMMENDED" ? rel : null,
    estimated_minutes: asNumber(row.estimated_minutes),
    learning_recommendation_id: row.learning_recommendation_id ?? null,
  };
}

function mapPlanRunSummary(dto: B9PlanRunDto): LiveLearningPlanRunSummary {
  return {
    id: dto.id,
    version_number: dto.version_number,
    status: dto.status,
    generation_source: dto.generation_source ?? null,
    algorithm_version: dto.algorithm_version ?? "B9_V1",
    source_evidence_hash: dto.source_evidence_hash ?? "",
    curriculum_graph_hash: dto.curriculum_graph_hash ?? "",
    input_hash: dto.input_hash ?? "",
    failure_code: dto.failure_code ?? null,
    failure_detail: dto.failure_detail ?? null,
    requested_at: dto.requested_at ?? null,
    finished_at: dto.finished_at ?? null,
  };
}

export function learningPlanApiToView(dto: B9LearningPlanDto): LiveLearningPlan {
  const pathRows = dto.path ?? dto.learning_path ?? [];
  return {
    run_id: dto.run_id ?? dto.id ?? "",
    version_number: dto.version_number,
    status: dto.status,
    generation_source: dto.generation_source ?? null,
    algorithm_version: dto.algorithm_version ?? "B9_V1",
    source_evidence_hash: dto.source_evidence_hash ?? "",
    curriculum_graph_hash: dto.curriculum_graph_hash ?? "",
    input_hash: dto.input_hash ?? "",
    is_stale: Boolean(dto.is_stale),
    recommendations: (dto.recommendations ?? []).map(mapRecommendation),
    path: pathRows
      .slice()
      .sort((a, b) => a.sequence - b.sequence)
      .map(mapPathStep),
    materialization_status: dto.materialization_status ?? null,
    evidence_coverage: {
      curriculum_node_count:
        dto.evidence_coverage?.curriculum_node_count ?? 0,
      evidence_row_count: dto.evidence_coverage?.evidence_row_count ?? 0,
    },
  };
}

function planFromRunDto(dto: B9PlanRunDto): LiveLearningPlan {
  return learningPlanApiToView({
    run_id: dto.id,
    id: dto.id,
    version_number: dto.version_number,
    status: dto.status,
    generation_source: dto.generation_source,
    algorithm_version: dto.algorithm_version,
    source_evidence_hash: dto.source_evidence_hash,
    curriculum_graph_hash: dto.curriculum_graph_hash,
    input_hash: dto.input_hash,
    is_stale: dto.is_stale,
    recommendations: dto.recommendations,
    path: dto.path,
    learning_path: dto.learning_path,
    materialization_status: dto.materialization_status,
    evidence_coverage: dto.evidence_coverage,
  });
}

function mapImprovementItem(
  row: B9ImprovementItemDto,
): LiveImprovementAssessmentItem {
  return {
    id: row.id,
    learning_recommendation_id: row.learning_recommendation_id ?? null,
    curriculum_node_id: row.curriculum_node_id,
    node_code: row.node_code ?? null,
    node_title: row.node_title ?? null,
    item_code: row.item_code,
    template_kind: row.template_kind,
    question_template_ref: row.question_template_ref,
    focus: row.focus,
    difficulty: row.difficulty,
    suggested_marks: asNumber(row.suggested_marks),
    sort_order: row.sort_order,
  };
}

export function improvementAssessmentApiToView(
  dto: B9ImprovementAssessmentDto,
): LiveImprovementAssessment {
  return {
    id: dto.id,
    student_id: dto.student_id,
    curriculum_id: dto.curriculum_id,
    learning_plan_run_id: dto.learning_plan_run_id,
    version_number: dto.version_number,
    title: dto.title,
    status: dto.status,
    generation_source: dto.generation_source ?? null,
    algorithm_version: dto.algorithm_version ?? null,
    source_evidence_hash: dto.source_evidence_hash ?? null,
    curriculum_graph_hash: dto.curriculum_graph_hash ?? null,
    input_hash: dto.input_hash ?? null,
    is_stale: Boolean(dto.is_stale),
    rejection_reason: dto.rejection_reason ?? null,
    failure_code: dto.failure_code ?? null,
    failure_detail: dto.failure_detail ?? null,
    items: (dto.items ?? [])
      .slice()
      .sort((a, b) => a.sort_order - b.sort_order)
      .map(mapImprovementItem),
    generated_at: dto.generated_at ?? null,
    approved_at: dto.approved_at ?? null,
    rejected_at: dto.rejected_at ?? null,
    created_at: dto.created_at ?? new Date().toISOString(),
  };
}

export function learningWorkspaceApiToView(
  dto: B9LearningWorkspaceDto,
): LiveLearningWorkspace {
  const latestPlan = dto.latest_plan
    ? learningPlanApiToView(dto.latest_plan)
    : dto.latest_run &&
        (dto.latest_run.recommendations || dto.latest_run.path)
      ? planFromRunDto(dto.latest_run)
      : null;

  const available = (dto.available_curricula ?? [])
    .map(mapCurriculum)
    .filter((c) => Boolean(c.id));

  let selected = dto.selected_curriculum
    ? mapCurriculum(dto.selected_curriculum)
    : null;
  if (!selected && dto.selected_curriculum_id) {
    selected =
      available.find((c) => c.id === dto.selected_curriculum_id) ?? null;
  }
  if (!selected && available.length === 1) {
    selected = available[0] ?? null;
  }

  return {
    student: {
      id: dto.student.id,
      display_name: dto.student.display_name,
      student_code: dto.student.student_code ?? null,
      external_ref: dto.student.external_ref ?? null,
    },
    available_curricula: available,
    selected_curriculum: selected,
    materialization_status: dto.materialization_status,
    evidence_coverage: {
      curriculum_node_count:
        dto.evidence_coverage?.curriculum_node_count ??
        dto.evidence_coverage?.node_count ??
        0,
      evidence_row_count:
        dto.evidence_coverage?.evidence_row_count ??
        dto.evidence_coverage?.evidence_count ??
        0,
    },
    latest_run: dto.latest_run ? mapPlanRunSummary(dto.latest_run) : null,
    latest_plan: latestPlan,
    is_stale: Boolean(dto.is_stale ?? latestPlan?.is_stale),
    latest_improvement_blueprint: dto.latest_improvement_blueprint
      ? improvementAssessmentApiToView(dto.latest_improvement_blueprint)
      : null,
  };
}

/**
 * Live B9 learning / improvement-blueprint HTTP adapter.
 */
export const LearningHttpApi = {
  async getLearningWorkspace(
    studentId: string,
    curriculumId?: string,
  ): Promise<LiveLearningWorkspace> {
    const params = new URLSearchParams();
    if (curriculumId) params.set("curriculum_id", curriculumId);
    const qs = params.toString();
    const path = `/api/v1/learning/students/${studentId}${qs ? `?${qs}` : ""}`;
    const dto = await httpRequest<B9LearningWorkspaceDto>(path);
    return learningWorkspaceApiToView(dto);
  },

  async prepareLearningPlan(
    studentId: string,
    curriculumId: string,
  ): Promise<LearningPlanPrepareResult> {
    const dto = await httpRequest<{
      run_id?: string;
      id?: string;
      student_id: string;
      curriculum_id: string;
      version_number: number;
      status: string;
      celery_task_id?: string | null;
      enqueue_error?: string | null;
      algorithm_version?: string;
      is_idempotent_reuse?: boolean;
    }>(`/api/v1/learning/students/${studentId}/prepare`, {
      method: "POST",
      body: { curriculum_id: curriculumId },
    });
    return {
      run_id: dto.run_id ?? dto.id ?? "",
      student_id: dto.student_id,
      curriculum_id: dto.curriculum_id,
      version_number: dto.version_number,
      status: dto.status,
      celery_task_id: dto.celery_task_id ?? null,
      enqueue_error: dto.enqueue_error ?? null,
      algorithm_version: dto.algorithm_version ?? "B9_V1",
      is_idempotent_reuse: Boolean(dto.is_idempotent_reuse),
    };
  },

  async getLearningPlanRun(runId: string): Promise<LiveLearningPlan> {
    const dto = await httpRequest<B9PlanRunDto>(
      `/api/v1/learning/plan-runs/${runId}`,
    );
    return planFromRunDto(dto);
  },

  async prepareImprovementBlueprint(
    runId: string,
  ): Promise<ImprovementBlueprintPrepareResult> {
    const dto = await httpRequest<{
      improvement_assessment_id?: string;
      id?: string;
      learning_plan_run_id: string;
      version_number: number;
      status: string;
      celery_task_id?: string | null;
      enqueue_error?: string | null;
    }>(
      `/api/v1/learning/plan-runs/${runId}/improvement-blueprints/prepare`,
      { method: "POST" },
    );
    return {
      improvement_assessment_id: dto.improvement_assessment_id ?? dto.id ?? "",
      learning_plan_run_id: dto.learning_plan_run_id,
      version_number: dto.version_number,
      status: dto.status,
      celery_task_id: dto.celery_task_id ?? null,
      enqueue_error: dto.enqueue_error ?? null,
    };
  },

  async getImprovementAssessment(
    id: string,
  ): Promise<LiveImprovementAssessment> {
    const dto = await httpRequest<B9ImprovementAssessmentDto>(
      `/api/v1/improvement-assessments/${id}`,
    );
    return improvementAssessmentApiToView(dto);
  },

  async approveImprovementBlueprint(
    id: string,
  ): Promise<LiveImprovementAssessment> {
    const dto = await httpRequest<B9ImprovementAssessmentDto>(
      `/api/v1/improvement-assessments/${id}/approve`,
      { method: "POST" },
    );
    return improvementAssessmentApiToView(dto);
  },

  async rejectImprovementBlueprint(
    id: string,
    reason: string,
  ): Promise<LiveImprovementAssessment> {
    const dto = await httpRequest<B9ImprovementAssessmentDto>(
      `/api/v1/improvement-assessments/${id}/reject`,
      { method: "POST", body: { reason } },
    );
    return improvementAssessmentApiToView(dto);
  },
};
