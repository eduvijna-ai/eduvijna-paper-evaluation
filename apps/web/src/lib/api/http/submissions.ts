import type {
  IdentityMatchState,
  IdentityReviewPayload,
  PaperPage,
  StudentMatchCandidate,
  Submission,
  SubmissionState,
  TranscriptionState,
} from "@/lib/types/domain";
import { ApiError } from "./errors";
import { getApiBaseUrl, httpRequest } from "./client";
import { clearAccessToken, getAccessToken } from "@/lib/auth/token-store";

/** Raw B3 submission JSON from the API. */
export interface B3SubmissionDto {
  id: string;
  tenant_id: string;
  assessment_id: string;
  assessment_version_id?: string;
  assessment_title?: string | null;
  student_id?: string | null;
  student_display_name?: string | null;
  workflow_state: string;
  student_match_state: string;
  roll_number_detected?: string | null;
  name_detected?: string | null;
  identity_confidence?: number | string | null;
  mapping_confidence?: number | string | null;
  source_content_sha256?: string | null;
  original_filename?: string | null;
  mime_type?: string | null;
  byte_size?: number | null;
  storage_status?: string | null;
  page_count?: number | null;
  bundle_name?: string | null;
  uploaded_at?: string | null;
  updated_at?: string | null;
  created_at?: string | null;
  transcription_state?: string | null;
}

export interface B3PaperPageDto {
  id: string;
  page_index?: number;
  page_number?: number;
  label?: string;
  width?: number | null;
  height?: number | null;
  is_continuation?: boolean;
}

export interface B3StudentMatchCandidateDto {
  student_id: string;
  display_name: string;
  external_ref?: string | null;
  grade?: string | null;
  section?: string | null;
  confidence?: number | string | null;
  match_reasons?: string[];
  source_type?: string;
}

export interface B3IdentityDetectedDto {
  name?: string | null;
  roll?: string | null;
  identity_confidence?: number | string | null;
}

export interface B3IdentityReviewDto {
  submission: B3SubmissionDto;
  pages?: B3PaperPageDto[];
  candidates?: B3StudentMatchCandidateDto[];
  automated_matching_active?: boolean;
  detected?: B3IdentityDetectedDto;
}

function asNumber(value: number | string | null | undefined, fallback = 0): number {
  if (value === null || value === undefined || value === "") return fallback;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

/** Map B3 submission dump → domain Submission. Exported for unit tests. */
export function submissionApiToView(dto: B3SubmissionDto): Submission {
  return {
    id: dto.id,
    tenant_id: dto.tenant_id,
    assessment_id: dto.assessment_id,
    assessment_title: dto.assessment_title ?? "—",
    student_id: dto.student_id ?? null,
    student_display_name: dto.student_display_name ?? null,
    roll_number_detected: dto.roll_number_detected ?? null,
    name_detected: dto.name_detected ?? null,
    workflow_state: dto.workflow_state as SubmissionState,
    student_match_state: dto.student_match_state as IdentityMatchState,
    identity_confidence: asNumber(dto.identity_confidence),
    mapping_confidence: asNumber(dto.mapping_confidence),
    page_count: asNumber(dto.page_count),
    uploaded_at: dto.uploaded_at ?? dto.created_at ?? "",
    updated_at: dto.updated_at ?? dto.uploaded_at ?? dto.created_at ?? "",
    original_filename: dto.original_filename ?? null,
    source_content_sha256: dto.source_content_sha256 ?? null,
    bundle_name: dto.bundle_name ?? null,
    mime_type: dto.mime_type ?? null,
    byte_size: dto.byte_size ?? null,
    storage_status: dto.storage_status ?? null,
    transcription_state: (dto.transcription_state ??
      "NOT_STARTED") as TranscriptionState,
  };
}

/** Map B3 page dump → domain PaperPage. Exported for unit tests. */
export function paperPageApiToView(dto: B3PaperPageDto): PaperPage {
  const pageNumber =
    dto.page_number ??
    (typeof dto.page_index === "number" ? dto.page_index + 1 : 1);
  return {
    id: dto.id,
    page_number: pageNumber,
    label: dto.label ?? `Page ${pageNumber}`,
    width: asNumber(dto.width, 800),
    height: asNumber(dto.height, 1100),
    ...(typeof dto.is_continuation === "boolean"
      ? { is_continuation: dto.is_continuation }
      : {}),
  };
}

function candidateApiToView(dto: B3StudentMatchCandidateDto): StudentMatchCandidate {
  return {
    student_id: dto.student_id,
    display_name: dto.display_name,
    external_ref: dto.external_ref ?? "",
    grade: dto.grade ?? "",
    section: dto.section ?? "",
    confidence: asNumber(dto.confidence),
    match_reasons: dto.match_reasons ?? [],
    source_type: dto.source_type,
  };
}

/** Map B3 identity payload → domain. Exported for unit tests. */
export function identityReviewApiToView(dto: B3IdentityReviewDto): IdentityReviewPayload {
  const detected = dto.detected;
  return {
    submission: submissionApiToView(dto.submission),
    pages: (dto.pages ?? []).map(paperPageApiToView),
    candidates: (dto.candidates ?? []).map(candidateApiToView),
    automated_matching_active: dto.automated_matching_active,
    detected: detected
      ? {
          name: detected.name ?? null,
          roll: detected.roll ?? null,
          identity_confidence: asNumber(detected.identity_confidence),
        }
      : undefined,
  };
}

async function fetchAuthenticatedBlob(path: string): Promise<Blob> {
  const headers = new Headers();
  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, { headers });
  } catch (err) {
    throw new ApiError({
      message: err instanceof Error ? err.message : "Network error",
      status: 0,
      kind: "network",
    });
  }

  if (!response.ok) {
    if (response.status === 401) {
      clearAccessToken();
    }
    let message = "Request failed";
    try {
      const json = (await response.json()) as {
        error?: { message?: string };
        detail?: { message?: string } | string;
        message?: string;
      };
      message =
        json.error?.message ??
        (typeof json.detail === "object" ? json.detail?.message : undefined) ??
        (typeof json.detail === "string" ? json.detail : undefined) ??
        json.message ??
        message;
    } catch {
      /* ignore body parse */
    }
    throw new ApiError({
      message,
      status: response.status,
      kind: ApiError.kindFromStatus(response.status),
    });
  }

  return response.blob();
}

export interface UploadSubmissionInput {
  assessmentId: string;
  bundleName?: string;
  file: File;
}

/**
 * Live B3 submission ingestion + identity review HTTP adapter.
 * Mapping review is handled by MappingHttpApi (B4).
 */
export const SubmissionHttpApi = {
  async listSubmissions(): Promise<Submission[]> {
    const rows = await httpRequest<B3SubmissionDto[]>("/api/v1/submissions");
    return rows.map(submissionApiToView);
  },

  async getSubmission(id: string): Promise<Submission> {
    const row = await httpRequest<B3SubmissionDto>(`/api/v1/submissions/${id}`);
    return submissionApiToView(row);
  },

  async getIdentityReview(submissionId: string): Promise<IdentityReviewPayload> {
    const payload = await httpRequest<B3IdentityReviewDto>(
      `/api/v1/submissions/${submissionId}/identity`,
    );
    return identityReviewApiToView(payload);
  },

  async confirmIdentity(submissionId: string, studentId: string): Promise<Submission> {
    const row = await httpRequest<B3SubmissionDto>(
      `/api/v1/submissions/${submissionId}/identity/confirm`,
      { method: "POST", body: { student_id: studentId } },
    );
    return submissionApiToView(row);
  },

  async markIdentityUnmatched(submissionId: string): Promise<Submission> {
    const row = await httpRequest<B3SubmissionDto>(
      `/api/v1/submissions/${submissionId}/identity/unmatched`,
      { method: "POST" },
    );
    return submissionApiToView(row);
  },

  async uploadSubmission(input: UploadSubmissionInput): Promise<Submission> {
    const form = new FormData();
    form.append("assessment_id", input.assessmentId);
    if (input.bundleName?.trim()) {
      form.append("bundle_name", input.bundleName.trim());
    }
    form.append("file", input.file, input.file.name);
    const row = await httpRequest<B3SubmissionDto>("/api/v1/submissions", {
      method: "POST",
      formData: form,
    });
    return submissionApiToView(row);
  },

  async getSubmissionPageImageBlob(pageId: string): Promise<Blob> {
    return fetchAuthenticatedBlob(`/api/v1/submission-pages/${pageId}/image`);
  },

  async getSubmissionSourceBlob(id: string): Promise<Blob> {
    return fetchAuthenticatedBlob(`/api/v1/submissions/${id}/source`);
  },
};
