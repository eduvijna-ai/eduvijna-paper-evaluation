import type {
  AnswerCluster,
  AnswerClusterDetail,
  AnswerClusterList,
  AnswerClusterReview,
  AnswerClusterRun,
  AnswerClusterRunList,
  OutcomeAttainmentReport,
  OutcomeAttainmentReportList,
  OutcomeDefinition,
  OutcomeDefinitionList,
  OutcomeMappingSet,
  OutcomeMappingSetList,
  QuestionOutcomeMapping,
} from "@/lib/types/domain";
import { clearAccessToken, getAccessToken } from "@/lib/auth/token-store";
import { ApiError } from "./errors";
import { getApiBaseUrl, httpRequest } from "./client";

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

function mapAnswerClusterRun(raw: Record<string, unknown>): AnswerClusterRun {
  return {
    id: String(raw.id),
    assessment_id: String(raw.assessment_id),
    assessment_version_id: String(raw.assessment_version_id),
    question_id: String(raw.question_id),
    question_version_id: String(raw.question_version_id),
    cohort_definition:
      (raw.cohort_definition as Record<string, unknown>) ?? {},
    algorithm_version: String(raw.algorithm_version ?? ""),
    similarity_threshold: asNumberRequired(raw.similarity_threshold as number),
    source_set_hash: String(raw.source_set_hash ?? ""),
    source_result_count: asNumberRequired(raw.source_result_count as number),
    source_published_result_ids: Array.isArray(raw.source_published_result_ids)
      ? raw.source_published_result_ids.map(String)
      : [],
    embedding_provider: String(raw.embedding_provider ?? ""),
    embedding_model: String(raw.embedding_model ?? ""),
    embedding_model_version: String(raw.embedding_model_version ?? ""),
    embedding_dim: asNumberRequired(raw.embedding_dim as number),
    cluster_count: asNumberRequired(raw.cluster_count as number),
    status: String(raw.status),
    requested_by: raw.requested_by ? String(raw.requested_by) : null,
    requested_at: raw.requested_at ? String(raw.requested_at) : null,
    completed_at: raw.completed_at ? String(raw.completed_at) : null,
    failure_code: raw.failure_code ? String(raw.failure_code) : null,
    failure_detail: raw.failure_detail ? String(raw.failure_detail) : null,
    created_at: raw.created_at ? String(raw.created_at) : null,
    updated_at: raw.updated_at ? String(raw.updated_at) : null,
  };
}

function mapAnswerCluster(raw: Record<string, unknown>): AnswerCluster {
  return {
    id: String(raw.id),
    run_id: String(raw.run_id),
    cluster_index: asNumberRequired(raw.cluster_index as number),
    member_count: asNumberRequired(raw.member_count as number),
    label: raw.label ? String(raw.label) : null,
    created_at: raw.created_at ? String(raw.created_at) : null,
  };
}

function mapAnswerClusterMember(
  raw: Record<string, unknown>,
): import("@/lib/types/domain").AnswerClusterMember {
  return {
    id: String(raw.id),
    run_id: String(raw.run_id),
    cluster_id: String(raw.cluster_id),
    published_result_id: String(raw.published_result_id),
    evaluation_run_id: String(raw.evaluation_run_id),
    question_evaluation_id: String(raw.question_evaluation_id),
    submission_id: String(raw.submission_id),
    transcription_text: raw.transcription_text
      ? String(raw.transcription_text)
      : null,
    transcription_hash: String(raw.transcription_hash ?? ""),
    embedding: Array.isArray(raw.embedding)
      ? raw.embedding.map((v) => asNumberRequired(v as number))
      : [],
    final_human_approved_score: asNumber(
      raw.final_human_approved_score as number,
    ),
    created_at: raw.created_at ? String(raw.created_at) : null,
  };
}

function mapAnswerClusterReview(
  raw: Record<string, unknown>,
): AnswerClusterReview {
  return {
    id: String(raw.id),
    run_id: String(raw.run_id),
    cluster_id: String(raw.cluster_id),
    reviewer_user_id: String(raw.reviewer_user_id),
    observation: String(raw.observation),
    suggested_rubric_refinement: raw.suggested_rubric_refinement
      ? String(raw.suggested_rubric_refinement)
      : null,
    submitted_at: raw.submitted_at ? String(raw.submitted_at) : null,
    created_at: raw.created_at ? String(raw.created_at) : null,
  };
}

function mapOutcomeDefinition(raw: Record<string, unknown>): OutcomeDefinition {
  return {
    id: String(raw.id),
    outcome_type: String(raw.outcome_type),
    code: String(raw.code),
    title: String(raw.title),
    description: raw.description ? String(raw.description) : null,
    status: String(raw.status),
    created_by: raw.created_by ? String(raw.created_by) : null,
    created_at: raw.created_at ? String(raw.created_at) : null,
    updated_at: raw.updated_at ? String(raw.updated_at) : null,
  };
}

function mapQuestionOutcomeMapping(
  raw: Record<string, unknown>,
): QuestionOutcomeMapping {
  return {
    id: String(raw.id),
    mapping_set_id: String(raw.mapping_set_id),
    question_id: String(raw.question_id),
    question_version_id: String(raw.question_version_id),
    outcome_definition_id: String(raw.outcome_definition_id),
    weight: asNumber(raw.weight as number),
    created_at: raw.created_at ? String(raw.created_at) : null,
  };
}

function mapOutcomeMappingSet(raw: Record<string, unknown>): OutcomeMappingSet {
  return {
    id: String(raw.id),
    assessment_id: String(raw.assessment_id),
    assessment_version_id: String(raw.assessment_version_id),
    version_number: asNumberRequired(raw.version_number as number, 1),
    title: String(raw.title),
    status: String(raw.status),
    created_by: raw.created_by ? String(raw.created_by) : null,
    activated_by: raw.activated_by ? String(raw.activated_by) : null,
    activated_at: raw.activated_at ? String(raw.activated_at) : null,
    retired_by: raw.retired_by ? String(raw.retired_by) : null,
    retired_at: raw.retired_at ? String(raw.retired_at) : null,
    created_at: raw.created_at ? String(raw.created_at) : null,
    updated_at: raw.updated_at ? String(raw.updated_at) : null,
    mapping_count:
      raw.mapping_count === undefined
        ? undefined
        : asNumberRequired(raw.mapping_count as number),
    mappings: Array.isArray(raw.mappings)
      ? (raw.mappings as Record<string, unknown>[]).map(mapQuestionOutcomeMapping)
      : undefined,
  };
}

function mapOutcomeAttainmentReport(
  raw: Record<string, unknown>,
): OutcomeAttainmentReport {
  return {
    id: String(raw.id),
    assessment_id: String(raw.assessment_id),
    assessment_version_id: String(raw.assessment_version_id),
    mapping_set_id: String(raw.mapping_set_id),
    mapping_set_version_number: asNumberRequired(
      raw.mapping_set_version_number as number,
      1,
    ),
    cohort_definition:
      (raw.cohort_definition as Record<string, unknown>) ?? {},
    algorithm_version: String(raw.algorithm_version ?? ""),
    source_set_hash: String(raw.source_set_hash ?? ""),
    source_result_count: asNumberRequired(raw.source_result_count as number),
    source_published_result_ids: Array.isArray(raw.source_published_result_ids)
      ? raw.source_published_result_ids.map(String)
      : [],
    status: String(raw.status),
    requested_by: raw.requested_by ? String(raw.requested_by) : null,
    requested_at: raw.requested_at ? String(raw.requested_at) : null,
    completed_at: raw.completed_at ? String(raw.completed_at) : null,
    failure_code: raw.failure_code ? String(raw.failure_code) : null,
    failure_detail: raw.failure_detail ? String(raw.failure_detail) : null,
    created_at: raw.created_at ? String(raw.created_at) : null,
    updated_at: raw.updated_at ? String(raw.updated_at) : null,
    metrics: Array.isArray(raw.metrics)
      ? (raw.metrics as Record<string, unknown>[]).map((row) => ({
          id: String(row.id),
          report_run_id: String(row.report_run_id),
          outcome_definition_id: String(row.outcome_definition_id),
          outcome_type: String(row.outcome_type),
          outcome_code: String(row.outcome_code),
          outcome_title: String(row.outcome_title),
          weighted_earned: asNumber(row.weighted_earned as number),
          weighted_max: asNumber(row.weighted_max as number),
          attainment_pct: asNumber(row.attainment_pct as number),
          denom_status: String(row.denom_status),
          mapped_question_count: asNumberRequired(
            row.mapped_question_count as number,
          ),
          contribution_count: asNumberRequired(
            row.contribution_count as number,
          ),
          created_at: row.created_at ? String(row.created_at) : null,
        }))
      : undefined,
  };
}

async function fetchAuthenticatedText(path: string): Promise<string> {
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

  return response.text();
}

export const OutcomeIntelligenceHttpApi = {
  async listAnswerClusterRuns(
    assessmentVersionId?: string,
    questionId?: string,
  ): Promise<AnswerClusterRunList> {
    const params = new URLSearchParams();
    if (assessmentVersionId) {
      params.set("assessment_version_id", assessmentVersionId);
    }
    if (questionId) {
      params.set("question_id", questionId);
    }
    const q = params.toString() ? `?${params.toString()}` : "";
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      `/api/v1/quality/answer-clusters/runs${q}`,
    );
    return { items: (raw.items ?? []).map(mapAnswerClusterRun) };
  },

  async createAnswerClusterRun(input: {
    assessment_version_id: string;
    question_id: string;
    similarity_threshold?: number;
  }): Promise<AnswerClusterRun> {
    const raw = await httpRequest<Record<string, unknown>>(
      "/api/v1/quality/answer-clusters/runs",
      { method: "POST", body: JSON.stringify(input) },
    );
    return mapAnswerClusterRun(raw);
  },

  async getAnswerClusterRun(runId: string): Promise<AnswerClusterRun> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/answer-clusters/runs/${runId}`,
    );
    return mapAnswerClusterRun(raw);
  },

  async listAnswerClusters(runId: string): Promise<AnswerClusterList> {
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      `/api/v1/quality/answer-clusters/runs/${runId}/clusters`,
    );
    return { items: (raw.items ?? []).map(mapAnswerCluster) };
  },

  async getAnswerCluster(clusterId: string): Promise<AnswerClusterDetail> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/answer-clusters/clusters/${clusterId}`,
    );
    return {
      ...mapAnswerCluster(raw),
      members: Array.isArray(raw.members)
        ? (raw.members as Record<string, unknown>[]).map(mapAnswerClusterMember)
        : [],
      reviews: Array.isArray(raw.reviews)
        ? (raw.reviews as Record<string, unknown>[]).map(mapAnswerClusterReview)
        : [],
    };
  },

  async submitAnswerClusterReview(
    clusterId: string,
    input: { observation: string; suggested_rubric_refinement?: string | null },
  ): Promise<AnswerClusterReview> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/answer-clusters/clusters/${clusterId}/reviews`,
      { method: "POST", body: JSON.stringify(input) },
    );
    return mapAnswerClusterReview(raw);
  },

  async listOutcomeDefinitions(
    outcomeType?: string,
  ): Promise<OutcomeDefinitionList> {
    const q = outcomeType
      ? `?outcome_type=${encodeURIComponent(outcomeType)}`
      : "";
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      `/api/v1/outcomes/definitions${q}`,
    );
    return { items: (raw.items ?? []).map(mapOutcomeDefinition) };
  },

  async createOutcomeDefinition(input: {
    outcome_type: string;
    code: string;
    title: string;
    description?: string | null;
  }): Promise<OutcomeDefinition> {
    const raw = await httpRequest<Record<string, unknown>>(
      "/api/v1/outcomes/definitions",
      { method: "POST", body: JSON.stringify(input) },
    );
    return mapOutcomeDefinition(raw);
  },

  async getOutcomeDefinition(id: string): Promise<OutcomeDefinition> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/outcomes/definitions/${id}`,
    );
    return mapOutcomeDefinition(raw);
  },

  async updateOutcomeDefinition(
    id: string,
    input: {
      title?: string;
      description?: string | null;
      status?: string;
    },
  ): Promise<OutcomeDefinition> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/outcomes/definitions/${id}`,
      { method: "PATCH", body: JSON.stringify(input) },
    );
    return mapOutcomeDefinition(raw);
  },

  async listOutcomeMappingSets(
    assessmentVersionId?: string,
  ): Promise<OutcomeMappingSetList> {
    const q = assessmentVersionId
      ? `?assessment_version_id=${encodeURIComponent(assessmentVersionId)}`
      : "";
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      `/api/v1/outcomes/mapping-sets${q}`,
    );
    return { items: (raw.items ?? []).map(mapOutcomeMappingSet) };
  },

  async createOutcomeMappingSet(input: {
    assessment_version_id: string;
    title: string;
  }): Promise<OutcomeMappingSet> {
    const raw = await httpRequest<Record<string, unknown>>(
      "/api/v1/outcomes/mapping-sets",
      { method: "POST", body: JSON.stringify(input) },
    );
    return mapOutcomeMappingSet(raw);
  },

  async getOutcomeMappingSet(id: string): Promise<OutcomeMappingSet> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/outcomes/mapping-sets/${id}`,
    );
    return mapOutcomeMappingSet(raw);
  },

  async addOutcomeMapping(
    mappingSetId: string,
    input: {
      question_id: string;
      outcome_definition_id: string;
      weight?: number;
    },
  ): Promise<QuestionOutcomeMapping> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/outcomes/mapping-sets/${mappingSetId}/mappings`,
      { method: "POST", body: JSON.stringify(input) },
    );
    return mapQuestionOutcomeMapping(raw);
  },

  async removeOutcomeMapping(mappingId: string): Promise<{ ok: true }> {
    return httpRequest(`/api/v1/outcomes/mappings/${mappingId}`, {
      method: "DELETE",
    });
  },

  async activateOutcomeMappingSet(
    mappingSetId: string,
  ): Promise<OutcomeMappingSet> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/outcomes/mapping-sets/${mappingSetId}/activate`,
      { method: "POST" },
    );
    return mapOutcomeMappingSet(raw);
  },

  async listOutcomeAttainmentReports(
    assessmentVersionId?: string,
  ): Promise<OutcomeAttainmentReportList> {
    const q = assessmentVersionId
      ? `?assessment_version_id=${encodeURIComponent(assessmentVersionId)}`
      : "";
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      `/api/v1/outcomes/attainment-reports${q}`,
    );
    return { items: (raw.items ?? []).map(mapOutcomeAttainmentReport) };
  },

  async createOutcomeAttainmentReport(input: {
    assessment_version_id: string;
    mapping_set_id?: string;
  }): Promise<OutcomeAttainmentReport> {
    const raw = await httpRequest<Record<string, unknown>>(
      "/api/v1/outcomes/attainment-reports",
      { method: "POST", body: JSON.stringify(input) },
    );
    return mapOutcomeAttainmentReport(raw);
  },

  async getOutcomeAttainmentReport(
    reportId: string,
  ): Promise<OutcomeAttainmentReport> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/outcomes/attainment-reports/${reportId}`,
    );
    return mapOutcomeAttainmentReport(raw);
  },

  async exportOutcomeAttainmentReportCsv(reportId: string): Promise<string> {
    return fetchAuthenticatedText(
      `/api/v1/outcomes/attainment-reports/${reportId}/export.csv`,
    );
  },
};
