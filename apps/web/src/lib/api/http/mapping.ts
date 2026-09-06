import type {
  EvidenceRegion,
  MappingNode,
  MappingReviewPayload,
  PaperPage,
  Question,
  QuestionAnswerMappingView,
  Submission,
} from "@/lib/types/domain";
import type { MappingNodeState } from "@/lib/types/enums";
import { httpRequest } from "./client";
import {
  paperPageApiToView,
  submissionApiToView,
  type B3PaperPageDto,
  type B3SubmissionDto,
} from "./submissions";

function asNumber(value: number | string | null | undefined, fallback = 0): number {
  if (value === null || value === undefined || value === "") return fallback;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

interface B4BBoxDto {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface B4AnswerRegionDto {
  id: string;
  page_id?: string;
  submission_page_id?: string;
  page_number?: number;
  label: string;
  bbox?: B4BBoxDto;
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  region_type?: string;
  source_type?: string;
  detection_confidence?: number | string | null;
  confidence?: number | string | null;
  crossed_out?: boolean;
  ignored?: boolean;
  is_continuation?: boolean;
  question_id?: string | null;
}

export interface B4QuestionDto {
  id: string;
  question_version_id?: string;
  question_id?: string;
  assessment_id: string;
  parent_id: string | null;
  code: string;
  prompt: string;
  max_mark?: number | string;
  sort_order: number;
  scoring_mode?: string;
  is_leaf_scorable?: boolean;
  curriculum_node_ids?: string[];
  children?: B4QuestionDto[];
}

export interface B4MappingNodeDto {
  question_id: string;
  question_code: string;
  region_ids: string[];
  confidence?: number | string | null;
  status: string;
}

export interface B4QuestionAnswerMappingDto {
  id: string;
  question_id: string;
  question_version_id: string;
  question_code: string;
  disposition: "ANSWERED" | "BLANK";
  mapping_state: "PROPOSED" | "REVIEW_REQUIRED" | "CONFIRMED";
  mapped_by: "HUMAN" | "AI";
  mapping_confidence?: number | string | null;
  region_ids: string[];
  confirmed_by?: string | null;
  confirmed_at?: string | null;
}

export interface B4MappingWorkspaceDto {
  submission: B3SubmissionDto;
  pages?: B3PaperPageDto[];
  regions?: B4AnswerRegionDto[];
  questions?: B4QuestionDto[];
  mapping?: B4MappingNodeDto[];
  mappings?: B4QuestionAnswerMappingDto[];
  completion?: {
    leaf_total: number;
    confirmed_count: number;
    unresolved_question_codes: string[];
  };
  assessment_version_id?: string;
  automated_region_detection_active?: boolean;
  automated_mapping_active?: boolean;
}

export function answerRegionApiToView(dto: B4AnswerRegionDto): EvidenceRegion {
  const bbox = dto.bbox;
  return {
    id: dto.id,
    page_id: dto.page_id ?? dto.submission_page_id ?? "",
    page_number: dto.page_number ?? 1,
    x: asNumber(dto.x ?? bbox?.x),
    y: asNumber(dto.y ?? bbox?.y),
    width: asNumber(dto.width ?? bbox?.width),
    height: asNumber(dto.height ?? bbox?.height),
    label: dto.label,
    confidence: asNumber(dto.confidence ?? dto.detection_confidence),
    question_id: dto.question_id ?? null,
    crossed_out: Boolean(dto.crossed_out),
    region_type: dto.region_type,
    source_type: dto.source_type,
    ignored: dto.ignored,
    is_continuation: dto.is_continuation,
  };
}

export function questionTreeApiToView(dto: B4QuestionDto): Question {
  return {
    id: dto.id,
    assessment_id: dto.assessment_id,
    parent_id: dto.parent_id,
    code: dto.code,
    prompt: dto.prompt,
    max_mark: asNumber(dto.max_mark),
    sort_order: dto.sort_order,
    curriculum_node_ids: dto.curriculum_node_ids ?? [],
    children: (dto.children ?? []).map(questionTreeApiToView),
    question_version_id: dto.question_version_id ?? dto.id,
    scoring_mode: dto.scoring_mode,
    is_leaf_scorable: dto.is_leaf_scorable,
  };
}

export function mappingNodeApiToView(dto: B4MappingNodeDto): MappingNode {
  return {
    question_id: dto.question_id,
    question_code: dto.question_code,
    region_ids: dto.region_ids ?? [],
    confidence: asNumber(dto.confidence),
    status: dto.status as MappingNodeState,
  };
}

export function questionMappingApiToView(
  dto: B4QuestionAnswerMappingDto,
): QuestionAnswerMappingView {
  return {
    id: dto.id,
    question_id: dto.question_id,
    question_version_id: dto.question_version_id,
    question_code: dto.question_code,
    disposition: dto.disposition,
    mapping_state: dto.mapping_state,
    mapped_by: dto.mapped_by,
    mapping_confidence: asNumber(dto.mapping_confidence),
    region_ids: dto.region_ids ?? [],
    confirmed_by: dto.confirmed_by ?? null,
    confirmed_at: dto.confirmed_at ?? null,
  };
}

/** Map B4 MappingWorkspace → domain MappingReviewPayload. Exported for unit tests. */
export function mappingWorkspaceApiToView(
  dto: B4MappingWorkspaceDto,
): MappingReviewPayload {
  const mappings = (dto.mappings ?? []).map(questionMappingApiToView);
  const mapping =
    (dto.mapping ?? []).map(mappingNodeApiToView).length > 0
      ? (dto.mapping ?? []).map(mappingNodeApiToView)
      : mappings.map((m) => ({
          question_id: m.question_version_id,
          question_code: m.question_code,
          region_ids: m.region_ids,
          confidence: m.mapping_confidence,
          status: m.mapping_state as MappingNodeState,
        }));

  return {
    submission: submissionApiToView(dto.submission),
    pages: (dto.pages ?? []).map(paperPageApiToView),
    regions: (dto.regions ?? []).map(answerRegionApiToView),
    mapping,
    questions: (dto.questions ?? []).map(questionTreeApiToView),
    mappings,
    completion: dto.completion,
    assessment_version_id: dto.assessment_version_id,
    automated_region_detection_active: dto.automated_region_detection_active,
    automated_mapping_active: dto.automated_mapping_active,
  };
}

export type CreateAnswerRegionInput = {
  label: string;
  region_type: "ANSWER" | "SCRATCH" | "DIAGRAM" | "IDENTITY";
  bbox: { x: number; y: number; width: number; height: number };
};

export type UpdateAnswerRegionInput = {
  label?: string;
  region_type?: "ANSWER" | "SCRATCH" | "DIAGRAM" | "IDENTITY";
  bbox?: { x: number; y: number; width: number; height: number };
  crossed_out?: boolean;
  ignored?: boolean;
  is_continuation?: boolean;
};

/**
 * Live B4 answer-region + question-mapping HTTP adapter.
 */
export const MappingHttpApi = {
  async prepareMappingReview(submissionId: string): Promise<Submission> {
    const row = await httpRequest<B3SubmissionDto>(
      `/api/v1/submissions/${submissionId}/mapping/prepare`,
      { method: "POST" },
    );
    return submissionApiToView(row);
  },

  async getMappingReview(submissionId: string): Promise<MappingReviewPayload> {
    const payload = await httpRequest<B4MappingWorkspaceDto>(
      `/api/v1/submissions/${submissionId}/mapping`,
    );
    return mappingWorkspaceApiToView(payload);
  },

  async createAnswerRegion(
    pageId: string,
    input: CreateAnswerRegionInput,
  ): Promise<EvidenceRegion> {
    const row = await httpRequest<B4AnswerRegionDto>(
      `/api/v1/submission-pages/${pageId}/answer-regions`,
      { method: "POST", body: input },
    );
    return answerRegionApiToView(row);
  },

  async updateAnswerRegion(
    regionId: string,
    input: UpdateAnswerRegionInput,
  ): Promise<EvidenceRegion> {
    const row = await httpRequest<B4AnswerRegionDto>(
      `/api/v1/answer-regions/${regionId}`,
      { method: "PATCH", body: input },
    );
    return answerRegionApiToView(row);
  },

  async deleteAnswerRegion(regionId: string): Promise<void> {
    await httpRequest<void>(`/api/v1/answer-regions/${regionId}`, {
      method: "DELETE",
    });
  },

  async updateSubmissionPage(
    pageId: string,
    input: { is_continuation: boolean },
  ): Promise<PaperPage> {
    const row = await httpRequest<B3PaperPageDto>(
      `/api/v1/submission-pages/${pageId}`,
      { method: "PATCH", body: input },
    );
    return paperPageApiToView(row);
  },

  async upsertQuestionMapping(
    submissionId: string,
    questionVersionId: string,
    input: { disposition: "ANSWERED" | "BLANK"; region_ids: string[] },
  ): Promise<QuestionAnswerMappingView> {
    const row = await httpRequest<B4QuestionAnswerMappingDto>(
      `/api/v1/submissions/${submissionId}/question-mappings/${questionVersionId}`,
      { method: "PUT", body: input },
    );
    return questionMappingApiToView(row);
  },

  async confirmQuestionMapping(
    submissionId: string,
    questionVersionId: string,
  ): Promise<QuestionAnswerMappingView> {
    const row = await httpRequest<B4QuestionAnswerMappingDto>(
      `/api/v1/submissions/${submissionId}/question-mappings/${questionVersionId}/confirm`,
      { method: "POST" },
    );
    return questionMappingApiToView(row);
  },

  async finalizeMappingReview(submissionId: string): Promise<Submission> {
    const row = await httpRequest<B3SubmissionDto>(
      `/api/v1/submissions/${submissionId}/mapping/finalize`,
      { method: "POST" },
    );
    return submissionApiToView(row);
  },
};
