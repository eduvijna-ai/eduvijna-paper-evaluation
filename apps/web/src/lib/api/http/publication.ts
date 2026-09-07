import type {
  AnnotatedPaperWorkspace,
  AnnotatedPaperQuestionScore,
  EvidenceRegion,
  ParentReport,
  PublicationAnnotation,
  PublicationArtifactType,
  PublicationPrepareResult,
  PublicationPublishResult,
  PublicationRegenerateResult,
  PublicationStatus,
  PublicationWorkspace,
  PublishedResultSummary,
  StudentReport,
  TeacherReport,
} from "@/lib/types/domain";
import { ApiError } from "./errors";
import { clearAccessToken, getAccessToken } from "@/lib/auth/token-store";
import { httpRequest } from "./client";
import { MappingHttpApi } from "./mapping";
import {
  parentReportApiToView,
  studentReportApiToView,
  teacherReportApiToView,
  type B7ParentReportDto,
  type B7StudentReportDto,
  type B7TeacherReportDto,
} from "./reports";

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

export interface B7ArtifactInfoDto {
  available?: boolean;
  sha256?: string | null;
  byte_size?: number | null;
}

export interface B7PublishedResultDto {
  id: string;
  submission_id: string;
  student_id?: string | null;
  assessment_id: string;
  assessment_version_id: string;
  evaluation_run_id: string;
  version_number: number;
  status: PublicationStatus | string;
  ledger_snapshot_hash: string;
  total_score?: number | string | null;
  max_total_score?: number | string | null;
  narrative_source?: "AI" | "FIXED" | "RULES_FALLBACK" | null;
  generated_at?: string | null;
  published_at?: string | null;
  failure_code?: string | null;
  failure_detail?: string | null;
  artifacts?: Partial<Record<PublicationArtifactType, B7ArtifactInfoDto>>;
}

export interface B7AnnotationDto {
  id: string;
  annotation_type: PublicationAnnotation["annotation_type"] | string;
  submission_page_id: string;
  question_evaluation_id?: string | null;
  answer_region_id?: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  payload?: Record<string, unknown>;
  source_type: string;
}

export interface B7PublicationWorkspaceDto {
  submission_id: string;
  workflow_state: string;
  latest: B7PublishedResultDto | null;
  versions: B7PublishedResultDto[];
  annotations: B7AnnotationDto[];
}

export interface B7PreparePublicationDto {
  submission_id: string;
  workflow_state: string;
  published_result_id: string;
  status: PublicationStatus | string;
  version_number: number;
  job_id?: string | null;
}

function publishedResultApiToView(dto: B7PublishedResultDto): PublishedResultSummary {
  const artifacts: PublishedResultSummary["artifacts"] = {};
  for (const [key, info] of Object.entries(dto.artifacts ?? {})) {
    artifacts[key as PublicationArtifactType] = {
      available: Boolean(info?.available),
      sha256: info?.sha256 ?? null,
      byte_size: info?.byte_size ?? null,
    };
  }
  return {
    id: dto.id,
    submission_id: dto.submission_id,
    student_id: dto.student_id ?? null,
    assessment_id: dto.assessment_id,
    assessment_version_id: dto.assessment_version_id,
    evaluation_run_id: dto.evaluation_run_id,
    version_number: dto.version_number,
    status: dto.status as PublicationStatus,
    ledger_snapshot_hash: dto.ledger_snapshot_hash,
    total_score: asNumber(dto.total_score),
    max_total_score: asNumber(dto.max_total_score),
    narrative_source: dto.narrative_source ?? null,
    generated_at: dto.generated_at ?? null,
    published_at: dto.published_at ?? null,
    failure_code: dto.failure_code ?? null,
    failure_detail: dto.failure_detail ?? null,
    artifacts,
  };
}

function annotationApiToView(dto: B7AnnotationDto): PublicationAnnotation {
  return {
    id: dto.id,
    annotation_type:
      dto.annotation_type as PublicationAnnotation["annotation_type"],
    submission_page_id: dto.submission_page_id,
    question_evaluation_id: dto.question_evaluation_id ?? null,
    answer_region_id: dto.answer_region_id ?? null,
    x: dto.x,
    y: dto.y,
    width: dto.width,
    height: dto.height,
    payload: dto.payload ?? {},
    source_type: dto.source_type,
  };
}

export function publicationWorkspaceApiToView(
  dto: B7PublicationWorkspaceDto,
): PublicationWorkspace {
  return {
    submission_id: dto.submission_id,
    workflow_state: dto.workflow_state,
    latest: dto.latest ? publishedResultApiToView(dto.latest) : null,
    versions: (dto.versions ?? []).map(publishedResultApiToView),
    annotations: (dto.annotations ?? []).map(annotationApiToView),
  };
}

function annotationKindFromType(
  type: string,
): EvidenceRegion["annotation_kind"] {
  switch (type) {
    case "TICK":
      return "FULL";
    case "PARTIAL":
    case "MARK":
      return "PARTIAL";
    case "CROSS":
      return "DEDUCTION";
    default:
      return "NEUTRAL";
  }
}

/** Convert publication annotations into paper-viewer evidence regions. */
export function annotationsToEvidenceRegions(
  annotations: PublicationAnnotation[],
  pageNumberById: Map<string, number>,
): EvidenceRegion[] {
  return annotations.map((ann) => {
    const finalMarks = asNumber(
      ann.payload.final_marks as number | string | null | undefined,
    );
    const maxMarks = asNumber(
      ann.payload.max_marks as number | string | null | undefined,
    );
    const reason =
      (typeof ann.payload.reason === "string" && ann.payload.reason) ||
      (typeof ann.payload.text === "string" && ann.payload.text) ||
      ann.annotation_type;
    const scoreLabel =
      finalMarks !== null && maxMarks !== null
        ? `${finalMarks}/${maxMarks}`
        : ann.annotation_type;
    return {
      id: ann.id,
      page_id: ann.submission_page_id,
      page_number: pageNumberById.get(ann.submission_page_id) ?? 1,
      x: ann.x,
      y: ann.y,
      width: ann.width,
      height: ann.height,
      label: scoreLabel,
      confidence: 1,
      question_id: ann.question_evaluation_id,
      crossed_out: false,
      annotation_kind: annotationKindFromType(ann.annotation_type),
      source_type: ann.source_type,
      region_type: "ANSWER",
    };
  });
}

function questionScoresFromAnnotations(
  annotations: PublicationAnnotation[],
): AnnotatedPaperQuestionScore[] {
  const byQe = new Map<string, AnnotatedPaperQuestionScore>();
  for (const ann of annotations) {
    const qeId = ann.question_evaluation_id;
    if (!qeId) continue;
    const final = asNumber(
      ann.payload.final_marks as number | string | null | undefined,
    );
    const max = asNumberRequired(
      ann.payload.max_marks as number | string | null | undefined,
      0,
    );
    const existing = byQe.get(qeId);
    if (!existing) {
      byQe.set(qeId, {
        id: qeId,
        question_code:
          (typeof ann.payload.criterion_code === "string" &&
            ann.payload.criterion_code) ||
          qeId.slice(0, 8),
        final_score: final,
        max_mark: max,
        feedback:
          typeof ann.payload.reason === "string" ? ann.payload.reason : null,
      });
      continue;
    }
    // Prefer MARK / aggregate max; keep first final when already set.
    if (existing.final_score === null && final !== null) {
      existing.final_score = final;
    }
    if (max > existing.max_mark) existing.max_mark = max;
  }
  return Array.from(byQe.values());
}

async function fetchArtifactBlob(
  publishedResultId: string,
  artifactType: PublicationArtifactType,
): Promise<Blob> {
  const API_BASE = (() => {
    const raw = process.env.NEXT_PUBLIC_API_BASE_URL;
    if (raw === undefined || raw === "" || raw === "same-origin") return "";
    return raw.replace(/\/$/, "");
  })();

  const headers = new Headers();
  headers.set("Accept", "application/pdf");
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  let response: Response;
  try {
    response = await fetch(
      `${API_BASE}/api/v1/publication-results/${publishedResultId}/artifacts/${artifactType}`,
      { method: "GET", headers },
    );
  } catch (err) {
    throw new ApiError({
      message: err instanceof Error ? err.message : "Network error",
      status: 0,
      kind: "network",
    });
  }

  if (!response.ok) {
    if (response.status === 401) clearAccessToken();
    let message = "Artifact download failed";
    try {
      const json = (await response.json()) as {
        detail?: { message?: string } | string;
        error?: { message?: string };
        message?: string;
      };
      message =
        (typeof json.detail === "object" ? json.detail?.message : undefined) ??
        (typeof json.detail === "string" ? json.detail : undefined) ??
        json.error?.message ??
        json.message ??
        message;
    } catch {
      /* ignore */
    }
    throw new ApiError({
      message,
      status: response.status,
      kind: ApiError.kindFromStatus(response.status),
    });
  }

  return response.blob();
}

/**
 * Live B7 publication / annotated-paper HTTP adapter.
 */
export const PublicationHttpApi = {
  async preparePublication(
    submissionId: string,
  ): Promise<PublicationPrepareResult> {
    const dto = await httpRequest<B7PreparePublicationDto>(
      `/api/v1/submissions/${submissionId}/publication/prepare`,
      { method: "POST" },
    );
    return {
      submission_id: dto.submission_id,
      workflow_state: dto.workflow_state,
      published_result_id: dto.published_result_id,
      status: dto.status as PublicationStatus,
      version_number: dto.version_number,
      job_id: dto.job_id ?? null,
    };
  },

  async getPublicationWorkspace(
    submissionId: string,
  ): Promise<PublicationWorkspace> {
    const dto = await httpRequest<B7PublicationWorkspaceDto>(
      `/api/v1/submissions/${submissionId}/publication`,
    );
    return publicationWorkspaceApiToView(dto);
  },

  async regeneratePublication(
    publishedResultId: string,
  ): Promise<PublicationRegenerateResult> {
    const dto = await httpRequest<{
      published_result_id: string;
      status: string;
      version_number: number;
      job_id: string;
      supersedes_result_id?: string | null;
    }>(`/api/v1/publication-results/${publishedResultId}/regenerate`, {
      method: "POST",
    });
    return {
      published_result_id: dto.published_result_id,
      status: dto.status,
      version_number: dto.version_number,
      job_id: dto.job_id,
      supersedes_result_id: dto.supersedes_result_id ?? null,
    };
  },

  async publishPublication(
    publishedResultId: string,
  ): Promise<PublicationPublishResult> {
    const dto = await httpRequest<{
      published_result_id: string;
      status: "PUBLISHED";
      submission_id: string;
      published_at?: string | null;
    }>(`/api/v1/publication-results/${publishedResultId}/publish`, {
      method: "POST",
    });
    return {
      published_result_id: dto.published_result_id,
      status: dto.status,
      submission_id: dto.submission_id,
      published_at: dto.published_at ?? null,
    };
  },

  getPublicationArtifactBlob: fetchArtifactBlob,

  async createPublicationAnnotation(
    publishedResultId: string,
    input: {
      annotation_type: "COMMENT" | "HIGHLIGHT";
      submission_page_id: string;
      x: number;
      y: number;
      width: number;
      height: number;
      payload?: Record<string, unknown>;
    },
  ): Promise<PublicationAnnotation> {
    const dto = await httpRequest<B7AnnotationDto>(
      `/api/v1/publication-results/${publishedResultId}/annotations`,
      {
        method: "POST",
        body: {
          annotation_type: input.annotation_type,
          submission_page_id: input.submission_page_id,
          x: input.x,
          y: input.y,
          width: input.width,
          height: input.height,
          payload: input.payload ?? {},
        },
      },
    );
    return annotationApiToView(dto);
  },

  async previewPublicationReport(
    publishedResultId: string,
    audience: "student" | "parent" | "teacher",
  ): Promise<StudentReport | ParentReport | TeacherReport> {
    if (audience === "student") {
      const dto = await httpRequest<B7StudentReportDto>(
        `/api/v1/publication-results/${publishedResultId}/reports/student`,
      );
      return studentReportApiToView(dto);
    }
    if (audience === "parent") {
      const dto = await httpRequest<B7ParentReportDto>(
        `/api/v1/publication-results/${publishedResultId}/reports/parent`,
      );
      return parentReportApiToView(dto);
    }
    const dto = await httpRequest<B7TeacherReportDto>(
      `/api/v1/publication-results/${publishedResultId}/reports/teacher`,
    );
    return teacherReportApiToView(dto);
  },

  async getAnnotatedPaperWorkspace(
    submissionId: string,
  ): Promise<AnnotatedPaperWorkspace> {
    const [workspace, mapping] = await Promise.all([
      PublicationHttpApi.getPublicationWorkspace(submissionId),
      MappingHttpApi.getMappingReview(submissionId),
    ]);

    const pageNumberById = new Map(
      mapping.pages.map((p) => [p.id, p.page_number] as const),
    );
    const regions = annotationsToEvidenceRegions(
      workspace.annotations,
      pageNumberById,
    );

    let questions = questionScoresFromAnnotations(workspace.annotations);

    // Prefer teacher report question codes / final scores when package is ready.
    const latest = workspace.latest;
    if (
      latest &&
      (latest.status === "GENERATED" || latest.status === "PUBLISHED")
    ) {
      try {
        const teacher = (await PublicationHttpApi.previewPublicationReport(
          latest.id,
          "teacher",
        )) as TeacherReport;
        questions = teacher.questions.map((q) => ({
          id: q.question_id,
          question_code: q.question_code,
          final_score: q.final_score,
          max_mark: q.max_mark,
          feedback: null,
        }));
      } catch {
        /* keep annotation-derived scores */
      }
    }

    return {
      submission_id: submissionId,
      workflow_state: workspace.workflow_state,
      pages: mapping.pages,
      regions,
      annotations: workspace.annotations,
      published_result: latest,
      questions,
      live: true,
    };
  },
};
