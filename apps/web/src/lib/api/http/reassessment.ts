import type {
  B14RebuildResult,
  Reassessment,
  ReassessmentInstantiateRequest,
  ReassessmentItem,
  ReassessmentMasteryDelta,
} from "@/lib/types/domain";
import { httpRequest } from "./client";

function asNumber(
  value: number | string | null | undefined,
): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

function asInt(
  value: number | string | null | undefined,
  fallback: number | null = 0,
): number | null {
  if (value === null || value === undefined || value === "") return fallback;
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.trunc(n);
}

export interface B14ReassessmentItemDto {
  id: string;
  improvement_assessment_item_id: string;
  question_version_id: string;
  curriculum_node_id: string;
  item_code_snapshot: string;
  template_kind_snapshot: string;
  question_template_ref_snapshot?: string | null;
}

export interface B14MasteryDeltaDto {
  curriculum_node_id: string;
  baseline_concept_mastery?: number | string | null;
  baseline_execution_accuracy?: number | string | null;
  baseline_concept_decisive_count?: number;
  baseline_execution_decisive_count?: number;
  baseline_concept_inconclusive_count?: number;
  baseline_execution_inconclusive_count?: number;
  baseline_evidence_count?: number;
  baseline_source_evidence_hash?: string;
  post_snapshot_id?: string | null;
  post_published_result_id?: string | null;
  post_concept_mastery?: number | string | null;
  post_execution_accuracy?: number | string | null;
  post_concept_decisive_count?: number | null;
  post_execution_decisive_count?: number | null;
  post_concept_inconclusive_count?: number | null;
  post_execution_inconclusive_count?: number | null;
  post_evidence_count?: number | null;
  post_source_evidence_hash?: string | null;
  concept_delta?: number | string | null;
  execution_delta?: number | string | null;
  materialized_at?: string | null;
  algorithm_version?: string;
}

export interface B14ReassessmentDto {
  id: string;
  improvement_assessment_id: string;
  blueprint_title?: string;
  blueprint_version_number?: number;
  student_id: string;
  curriculum_id: string;
  assessment_id: string;
  assessment_status?: string;
  assessment_version_id: string;
  submission_id?: string | null;
  published_result_id?: string | null;
  status: string;
  algorithm_version?: string;
  instantiation_hash?: string;
  baseline_captured_at?: string;
  created_at?: string;
  updated_at?: string;
  items?: B14ReassessmentItemDto[];
  mastery_deltas?: B14MasteryDeltaDto[];
}

export interface B14RebuildResultDto {
  reassessment_id: string;
  algorithm_version?: string;
  delta_count?: number;
  published_result_id?: string | null;
  source?: string;
}

export function reassessmentItemApiToView(
  dto: B14ReassessmentItemDto,
): ReassessmentItem {
  return {
    id: dto.id,
    improvement_assessment_item_id: dto.improvement_assessment_item_id,
    question_version_id: dto.question_version_id,
    curriculum_node_id: dto.curriculum_node_id,
    item_code_snapshot: dto.item_code_snapshot,
    template_kind_snapshot: dto.template_kind_snapshot,
    question_template_ref_snapshot: dto.question_template_ref_snapshot ?? null,
  };
}

export function reassessmentMasteryDeltaApiToView(
  dto: B14MasteryDeltaDto,
): ReassessmentMasteryDelta {
  return {
    curriculum_node_id: dto.curriculum_node_id,
    baseline_concept_mastery: asNumber(dto.baseline_concept_mastery),
    baseline_execution_accuracy: asNumber(dto.baseline_execution_accuracy),
    baseline_concept_decisive_count:
      asInt(dto.baseline_concept_decisive_count, 0) ?? 0,
    baseline_execution_decisive_count:
      asInt(dto.baseline_execution_decisive_count, 0) ?? 0,
    baseline_concept_inconclusive_count:
      asInt(dto.baseline_concept_inconclusive_count, 0) ?? 0,
    baseline_execution_inconclusive_count:
      asInt(dto.baseline_execution_inconclusive_count, 0) ?? 0,
    baseline_evidence_count: asInt(dto.baseline_evidence_count, 0) ?? 0,
    baseline_source_evidence_hash: dto.baseline_source_evidence_hash ?? "",
    post_snapshot_id: dto.post_snapshot_id ?? null,
    post_published_result_id: dto.post_published_result_id ?? null,
    post_concept_mastery: asNumber(dto.post_concept_mastery),
    post_execution_accuracy: asNumber(dto.post_execution_accuracy),
    post_concept_decisive_count: asInt(dto.post_concept_decisive_count, null),
    post_execution_decisive_count: asInt(
      dto.post_execution_decisive_count,
      null,
    ),
    post_concept_inconclusive_count: asInt(
      dto.post_concept_inconclusive_count,
      null,
    ),
    post_execution_inconclusive_count: asInt(
      dto.post_execution_inconclusive_count,
      null,
    ),
    post_evidence_count: asInt(dto.post_evidence_count, null),
    post_source_evidence_hash: dto.post_source_evidence_hash ?? null,
    concept_delta: asNumber(dto.concept_delta),
    execution_delta: asNumber(dto.execution_delta),
    materialized_at: dto.materialized_at ?? null,
    algorithm_version: dto.algorithm_version ?? "B14_V1",
  };
}

export function reassessmentApiToView(dto: B14ReassessmentDto): Reassessment {
  return {
    id: dto.id,
    improvement_assessment_id: dto.improvement_assessment_id,
    blueprint_title: dto.blueprint_title ?? "",
    blueprint_version_number: dto.blueprint_version_number ?? 1,
    student_id: dto.student_id,
    curriculum_id: dto.curriculum_id,
    assessment_id: dto.assessment_id,
    assessment_status: dto.assessment_status ?? "DRAFT",
    assessment_version_id: dto.assessment_version_id,
    submission_id: dto.submission_id ?? null,
    published_result_id: dto.published_result_id ?? null,
    status: dto.status,
    algorithm_version: dto.algorithm_version ?? "B14_V1",
    instantiation_hash: dto.instantiation_hash ?? "",
    baseline_captured_at:
      dto.baseline_captured_at ?? dto.created_at ?? new Date().toISOString(),
    created_at: dto.created_at ?? new Date().toISOString(),
    updated_at: dto.updated_at ?? dto.created_at ?? new Date().toISOString(),
    items: (dto.items ?? []).map(reassessmentItemApiToView),
    mastery_deltas: (dto.mastery_deltas ?? []).map(
      reassessmentMasteryDeltaApiToView,
    ),
  };
}

export function b14RebuildResultApiToView(
  dto: B14RebuildResultDto,
): B14RebuildResult {
  return {
    reassessment_id: dto.reassessment_id,
    algorithm_version: dto.algorithm_version ?? "B14_V1",
    delta_count: dto.delta_count ?? 0,
    published_result_id: dto.published_result_id ?? null,
    source: dto.source ?? "MASTERY_STATE_SNAPSHOT",
  };
}

/** Live B14 reassessment HTTP adapter. */
export const ReassessmentHttpApi = {
  async instantiateReassessment(
    blueprintId: string,
    input: ReassessmentInstantiateRequest,
  ): Promise<Reassessment> {
    const dto = await httpRequest<B14ReassessmentDto>(
      `/api/v1/improvement-assessments/${blueprintId}/reassessment`,
      { method: "POST", body: input },
    );
    return reassessmentApiToView(dto);
  },

  async getReassessment(id: string): Promise<Reassessment> {
    const dto = await httpRequest<B14ReassessmentDto>(
      `/api/v1/reassessments/${id}`,
    );
    return reassessmentApiToView(dto);
  },

  async rebuildReassessmentB14(id: string): Promise<B14RebuildResult> {
    const dto = await httpRequest<B14RebuildResultDto>(
      `/api/v1/reassessments/${id}/b14/rebuild`,
      { method: "POST" },
    );
    return b14RebuildResultApiToView(dto);
  },
};
