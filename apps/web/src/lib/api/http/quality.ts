import type {
  CalibrationCaseBlind,
  CalibrationEvaluatorMetric,
  CalibrationResponse,
  CalibrationSession,
  CalibrationSessionList,
  CalibrationSessionMetric,
  ItemPsychometricMetricList,
  PsychometricRun,
  PsychometricRunList,
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

function mapPsychometricRun(raw: Record<string, unknown>): PsychometricRun {
  return {
    id: String(raw.id),
    assessment_id: String(raw.assessment_id),
    assessment_version_id: String(raw.assessment_version_id),
    cohort_definition:
      (raw.cohort_definition as Record<string, unknown>) ?? {},
    algorithm_version: String(raw.algorithm_version ?? ""),
    min_cohort_size: asNumberRequired(raw.min_cohort_size as number, 20),
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
  };
}

function mapCalibrationSession(raw: Record<string, unknown>): CalibrationSession {
  return {
    id: String(raw.id),
    assessment_id: String(raw.assessment_id),
    assessment_version_id: String(raw.assessment_version_id),
    title: String(raw.title ?? ""),
    status: String(raw.status),
    algorithm_version: String(raw.algorithm_version ?? ""),
    score_tolerance_abs: asNumberRequired(raw.score_tolerance_abs as number),
    score_tolerance_pct: asNumberRequired(raw.score_tolerance_pct as number),
    min_cases: asNumberRequired(raw.min_cases as number, 10),
    activated_by: raw.activated_by ? String(raw.activated_by) : null,
    activated_at: raw.activated_at ? String(raw.activated_at) : null,
    closed_by: raw.closed_by ? String(raw.closed_by) : null,
    closed_at: raw.closed_at ? String(raw.closed_at) : null,
    created_by: raw.created_by ? String(raw.created_by) : null,
    created_at: raw.created_at ? String(raw.created_at) : null,
    updated_at: raw.updated_at ? String(raw.updated_at) : null,
    case_count:
      raw.case_count === undefined
        ? undefined
        : asNumberRequired(raw.case_count as number),
    cases: Array.isArray(raw.cases)
      ? (raw.cases as Record<string, unknown>[]).map((c) => ({
          id: String(c.id),
          session_id: String(c.session_id),
          case_code: String(c.case_code),
          published_result_id: String(c.published_result_id),
          evaluation_run_id: String(c.evaluation_run_id),
          question_evaluation_id: String(c.question_evaluation_id),
          question_version_id: String(c.question_version_id),
          rubric_version_id: String(c.rubric_version_id),
          max_mark: asNumberRequired(c.max_mark as number),
          reference_score: asNumberRequired(c.reference_score as number),
          source_snapshot_hash: String(c.source_snapshot_hash ?? ""),
          created_at: c.created_at ? String(c.created_at) : null,
        }))
      : undefined,
    participants: Array.isArray(raw.participants)
      ? (raw.participants as { id: string; user_id: string }[]).map((p) => ({
          id: String(p.id),
          user_id: String(p.user_id),
        }))
      : undefined,
  };
}

export const QualityHttpApi = {
  async listPsychometricRuns(
    assessmentVersionId?: string,
  ): Promise<PsychometricRunList> {
    const q = assessmentVersionId
      ? `?assessment_version_id=${encodeURIComponent(assessmentVersionId)}`
      : "";
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      `/api/v1/quality/psychometrics/runs${q}`,
    );
    return { items: (raw.items ?? []).map(mapPsychometricRun) };
  },

  async createPsychometricRun(
    assessmentVersionId: string,
  ): Promise<PsychometricRun> {
    const raw = await httpRequest<Record<string, unknown>>(
      "/api/v1/quality/psychometrics/runs",
      {
        method: "POST",
        body: JSON.stringify({ assessment_version_id: assessmentVersionId }),
      },
    );
    return mapPsychometricRun(raw);
  },

  async getPsychometricRun(runId: string): Promise<PsychometricRun> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/psychometrics/runs/${runId}`,
    );
    return mapPsychometricRun(raw);
  },

  async listPsychometricRunItems(
    runId: string,
  ): Promise<ItemPsychometricMetricList> {
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      `/api/v1/quality/psychometrics/runs/${runId}/items`,
    );
    return {
      items: (raw.items ?? []).map((row) => ({
        id: String(row.id),
        run_id: String(row.run_id),
        question_id: String(row.question_id),
        question_version_id: String(row.question_version_id),
        question_code: String(row.question_code),
        attempt_count: asNumberRequired(row.attempt_count as number),
        max_mark: asNumberRequired(row.max_mark as number),
        mean_raw_score: asNumberRequired(row.mean_raw_score as number),
        std_dev: asNumberRequired(row.std_dev as number),
        difficulty_index: asNumberRequired(row.difficulty_index as number),
        discrimination_index: asNumber(row.discrimination_index as number),
        discrimination_method: String(row.discrimination_method ?? ""),
        discrimination_status: String(row.discrimination_status ?? ""),
        full_credit_rate: asNumberRequired(row.full_credit_rate as number),
        zero_score_rate: asNumberRequired(row.zero_score_rate as number),
        blank_rate: asNumber(row.blank_rate as number),
        difficulty_band: row.difficulty_band
          ? String(row.difficulty_band)
          : null,
        discrimination_band: row.discrimination_band
          ? String(row.discrimination_band)
          : null,
      })),
    };
  },

  async getLatestPsychometricRun(
    assessmentVersionId: string,
  ): Promise<PsychometricRun> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/psychometrics/latest?assessment_version_id=${encodeURIComponent(assessmentVersionId)}`,
    );
    return mapPsychometricRun(raw);
  },

  async listCalibrationSessions(): Promise<CalibrationSessionList> {
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      "/api/v1/quality/calibration/sessions",
    );
    return { items: (raw.items ?? []).map(mapCalibrationSession) };
  },

  async createCalibrationSession(input: {
    assessment_version_id: string;
    title: string;
    score_tolerance_abs?: number;
    score_tolerance_pct?: number;
    min_cases?: number;
  }): Promise<CalibrationSession> {
    const raw = await httpRequest<Record<string, unknown>>(
      "/api/v1/quality/calibration/sessions",
      { method: "POST", body: JSON.stringify(input) },
    );
    return mapCalibrationSession(raw);
  },

  async getCalibrationSession(sessionId: string): Promise<CalibrationSession> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/calibration/sessions/${sessionId}`,
    );
    return mapCalibrationSession(raw);
  },

  async activateCalibrationSession(
    sessionId: string,
  ): Promise<CalibrationSession> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/calibration/sessions/${sessionId}/activate`,
      { method: "POST" },
    );
    return mapCalibrationSession(raw);
  },

  async closeCalibrationSession(
    sessionId: string,
  ): Promise<CalibrationSession> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/calibration/sessions/${sessionId}/close`,
      { method: "POST" },
    );
    return mapCalibrationSession(raw);
  },

  async listMyCalibrationSessions(): Promise<CalibrationSessionList> {
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      "/api/v1/quality/calibration/my-sessions",
    );
    return { items: (raw.items ?? []).map(mapCalibrationSession) };
  },

  async getBlindCalibrationCase(
    sessionId: string,
    caseId: string,
  ): Promise<CalibrationCaseBlind> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/calibration/sessions/${sessionId}/cases/${caseId}/blind`,
    );
    return {
      id: String(raw.id),
      session_id: String(raw.session_id),
      case_code: String(raw.case_code),
      question_version_id: String(raw.question_version_id),
      rubric_version_id: String(raw.rubric_version_id),
      max_mark: asNumberRequired(raw.max_mark as number),
      criterion_snapshot: Array.isArray(raw.criterion_snapshot)
        ? raw.criterion_snapshot
        : [],
      evidence_snapshot:
        (raw.evidence_snapshot as Record<string, unknown>) ?? {},
    };
  },

  async submitCalibrationResponse(
    sessionId: string,
    caseId: string,
    input: { score: number; comment?: string | null },
  ): Promise<CalibrationResponse> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/calibration/sessions/${sessionId}/cases/${caseId}/responses`,
      { method: "POST", body: JSON.stringify(input) },
    );
    return {
      id: String(raw.id),
      session_id: String(raw.session_id),
      case_id: String(raw.case_id),
      participant_id: String(raw.participant_id),
      user_id: String(raw.user_id),
      score: asNumberRequired(raw.score as number),
      max_mark: asNumberRequired(raw.max_mark as number),
      comment: raw.comment ? String(raw.comment) : null,
      submitted_at: raw.submitted_at ? String(raw.submitted_at) : null,
    };
  },

  async getCalibrationProgress(sessionId: string): Promise<{
    case_count: number;
    participant_count: number;
    response_count: number;
    status: string;
  }> {
    return httpRequest(
      `/api/v1/quality/calibration/sessions/${sessionId}/progress`,
    );
  },

  async getCalibrationSessionMetrics(
    sessionId: string,
  ): Promise<{ items: CalibrationSessionMetric[] }> {
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      `/api/v1/quality/calibration/sessions/${sessionId}/metrics`,
    );
    return {
      items: (raw.items ?? []).map((row) => ({
        id: String(row.id),
        session_id: String(row.session_id),
        metric_name: String(row.metric_name),
        algorithm_version: String(row.algorithm_version),
        evaluator_count: asNumberRequired(row.evaluator_count as number),
        common_case_count: asNumberRequired(row.common_case_count as number),
        icc_value: asNumber(row.icc_value as number),
        status: String(row.status),
      })),
    };
  },

  async getCalibrationEvaluatorMetrics(
    sessionId: string,
  ): Promise<{ items: CalibrationEvaluatorMetric[] }> {
    const raw = await httpRequest<{ items?: Record<string, unknown>[] }>(
      `/api/v1/quality/calibration/sessions/${sessionId}/evaluator-metrics`,
    );
    return {
      items: (raw.items ?? []).map((row) => ({
        id: String(row.id),
        session_id: String(row.session_id),
        user_id: String(row.user_id),
        case_count: asNumberRequired(row.case_count as number),
        mean_signed_diff: asNumberRequired(row.mean_signed_diff as number),
        mae: asNumberRequired(row.mae as number),
        nmae: asNumberRequired(row.nmae as number),
        exact_match_rate: asNumberRequired(row.exact_match_rate as number),
        within_tolerance_rate: asNumberRequired(
          row.within_tolerance_rate as number,
        ),
      })),
    };
  },

  async getMyCalibrationMetrics(
    sessionId: string,
  ): Promise<CalibrationEvaluatorMetric> {
    const raw = await httpRequest<Record<string, unknown>>(
      `/api/v1/quality/calibration/sessions/${sessionId}/my-metrics`,
    );
    return {
      id: String(raw.id),
      session_id: String(raw.session_id),
      user_id: String(raw.user_id),
      case_count: asNumberRequired(raw.case_count as number),
      mean_signed_diff: asNumberRequired(raw.mean_signed_diff as number),
      mae: asNumberRequired(raw.mae as number),
      nmae: asNumberRequired(raw.nmae as number),
      exact_match_rate: asNumberRequired(raw.exact_match_rate as number),
      within_tolerance_rate: asNumberRequired(
        raw.within_tolerance_rate as number,
      ),
    };
  },
};
