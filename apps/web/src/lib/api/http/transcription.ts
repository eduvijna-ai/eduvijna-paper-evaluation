import type {
  RegionTranscriptionView,
  Submission,
  SubmissionState,
  TranscriptionQuestionItem,
  TranscriptionRegionView,
  TranscriptionState,
  TranscriptionWorkspacePayload,
} from "@/lib/types/domain";
import { getApiBaseUrl, httpRequest } from "./client";
import {
  submissionApiToView,
  type B3SubmissionDto,
} from "./submissions";
import { ApiError } from "./errors";
import { clearAccessToken, getAccessToken } from "@/lib/auth/token-store";

function asNumber(value: number | string | null | undefined, fallback = 0): number {
  if (value === null || value === undefined || value === "") return fallback;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

export interface B5RegionTranscriptionDto {
  id: string;
  answer_region_id: string;
  version_number: number;
  source_type: string;
  text?: string | null;
  latex?: string | null;
  segments?: unknown[];
  transcription_confidence?: number | string | null;
  unreadable: boolean;
  visual_only: boolean;
  status: string;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface B5TranscriptionRegionDto {
  id: string;
  label: string;
  region_type?: string;
  source_type?: string;
  detection_confidence?: number | string | null;
  bbox?: { x: number; y: number; width: number; height: number };
  crop_url?: string | null;
  page_image_url?: string | null;
  page_index?: number | null;
  latest_ai_proposal?: B5RegionTranscriptionDto | null;
  active_transcription?: B5RegionTranscriptionDto | null;
  requires_transcription?: boolean;
}

export interface B5TranscriptionQuestionItemDto {
  question_version_id: string;
  question_label: string;
  disposition: "ANSWERED" | "BLANK";
  mapping_state: string;
  regions: B5TranscriptionRegionDto[];
  requires_transcription?: boolean;
}

export interface B5TranscriptionWorkspaceDto {
  submission_id: string;
  workflow_state: string;
  transcription_state: string;
  automated_transcription_active?: boolean;
  progress?: {
    reviewed: number;
    required: number;
    label?: string;
  };
  items: B5TranscriptionQuestionItemDto[];
}

export interface B5PrepareTranscriptionDto {
  submission_id: string;
  workflow_state: string;
  transcription_state: string;
  job_id?: string | null;
}

export interface B5FinalizeTranscriptionDto {
  submission_id: string;
  workflow_state: string;
  transcription_state: string;
  evaluation_enqueued?: boolean;
}

export type PutRegionTranscriptionInput = {
  text?: string | null;
  latex?: string | null;
  unreadable?: boolean;
  visual_only?: boolean;
  outcome?: "TRANSCRIBED" | "UNREADABLE" | "VISUAL_ONLY";
};

export function regionTranscriptionApiToView(
  dto: B5RegionTranscriptionDto,
): RegionTranscriptionView {
  const confidence = dto.transcription_confidence;
  return {
    id: dto.id,
    answer_region_id: dto.answer_region_id,
    version_number: dto.version_number,
    source_type: dto.source_type,
    text: dto.text ?? null,
    latex: dto.latex ?? null,
    transcription_confidence:
      confidence === null || confidence === undefined
        ? null
        : asNumber(confidence),
    unreadable: Boolean(dto.unreadable),
    visual_only: Boolean(dto.visual_only),
    status: dto.status,
    confirmed_by: dto.confirmed_by ?? null,
    confirmed_at: dto.confirmed_at ?? null,
  };
}

export function transcriptionRegionApiToView(
  dto: B5TranscriptionRegionDto,
): TranscriptionRegionView {
  const bbox = dto.bbox ?? { x: 0, y: 0, width: 0, height: 0 };
  return {
    id: dto.id,
    label: dto.label,
    region_type: dto.region_type,
    source_type: dto.source_type,
    detection_confidence: asNumber(dto.detection_confidence),
    bbox: {
      x: asNumber(bbox.x),
      y: asNumber(bbox.y),
      width: asNumber(bbox.width),
      height: asNumber(bbox.height),
    },
    crop_url: dto.crop_url ?? null,
    page_image_url: dto.page_image_url ?? null,
    page_index: dto.page_index ?? null,
    latest_ai_proposal: dto.latest_ai_proposal
      ? regionTranscriptionApiToView(dto.latest_ai_proposal)
      : null,
    active_transcription: dto.active_transcription
      ? regionTranscriptionApiToView(dto.active_transcription)
      : null,
    requires_transcription: Boolean(dto.requires_transcription),
  };
}

function questionItemApiToView(
  dto: B5TranscriptionQuestionItemDto,
): TranscriptionQuestionItem {
  return {
    question_version_id: dto.question_version_id,
    question_label: dto.question_label,
    disposition: dto.disposition,
    mapping_state: dto.mapping_state,
    regions: (dto.regions ?? []).map(transcriptionRegionApiToView),
    requires_transcription: Boolean(dto.requires_transcription),
  };
}

/** Map B5 transcription workspace → domain view. Exported for unit tests. */
export function transcriptionWorkspaceApiToView(
  dto: B5TranscriptionWorkspaceDto,
): TranscriptionWorkspacePayload {
  const reviewed = dto.progress?.reviewed ?? 0;
  const required = dto.progress?.required ?? 0;
  return {
    submission_id: dto.submission_id,
    workflow_state: dto.workflow_state as SubmissionState,
    transcription_state: dto.transcription_state as TranscriptionState,
    automated_transcription_active: Boolean(dto.automated_transcription_active),
    progress: {
      reviewed,
      required,
      label:
        dto.progress?.label ?? `${reviewed} of ${required} evidence regions reviewed`,
    },
    items: (dto.items ?? []).map(questionItemApiToView),
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
        detail?: { message?: string } | string;
        message?: string;
      };
      message =
        (typeof json.detail === "object" ? json.detail?.message : undefined) ??
        (typeof json.detail === "string" ? json.detail : undefined) ??
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
 * Live B5 transcription review HTTP adapter.
 */
export const TranscriptionHttpApi = {
  async prepareTranscription(submissionId: string): Promise<Submission> {
    const row = await httpRequest<B5PrepareTranscriptionDto>(
      `/api/v1/submissions/${submissionId}/transcription/prepare`,
      { method: "POST" },
    );
    const submission = await httpRequest<B3SubmissionDto>(
      `/api/v1/submissions/${submissionId}`,
    );
    return submissionApiToView({
      ...submission,
      transcription_state: row.transcription_state,
      workflow_state: row.workflow_state,
    });
  },

  async getTranscriptionWorkspace(
    submissionId: string,
  ): Promise<TranscriptionWorkspacePayload> {
    const payload = await httpRequest<B5TranscriptionWorkspaceDto>(
      `/api/v1/submissions/${submissionId}/transcription`,
    );
    return transcriptionWorkspaceApiToView(payload);
  },

  async putRegionTranscription(
    regionId: string,
    input: PutRegionTranscriptionInput,
  ): Promise<RegionTranscriptionView> {
    const row = await httpRequest<B5RegionTranscriptionDto>(
      `/api/v1/answer-regions/${regionId}/transcription`,
      { method: "PUT", body: input },
    );
    return regionTranscriptionApiToView(row);
  },

  async confirmTranscription(
    transcriptionId: string,
  ): Promise<RegionTranscriptionView> {
    const row = await httpRequest<B5RegionTranscriptionDto>(
      `/api/v1/answer-region-transcriptions/${transcriptionId}/confirm`,
      { method: "POST" },
    );
    return regionTranscriptionApiToView(row);
  },

  async finalizeTranscription(submissionId: string): Promise<Submission> {
    const row = await httpRequest<B5FinalizeTranscriptionDto>(
      `/api/v1/submissions/${submissionId}/transcription/finalize`,
      { method: "POST" },
    );
    const submission = await httpRequest<B3SubmissionDto>(
      `/api/v1/submissions/${submissionId}`,
    );
    return submissionApiToView({
      ...submission,
      transcription_state: row.transcription_state,
      workflow_state: row.workflow_state,
    });
  },

  async getRegionCropBlob(regionId: string): Promise<Blob> {
    return fetchAuthenticatedBlob(`/api/v1/answer-regions/${regionId}/crop`);
  },
};
