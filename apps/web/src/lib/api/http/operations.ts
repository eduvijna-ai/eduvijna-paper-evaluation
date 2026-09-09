/** B16 enterprise operations HTTP adapter. */

import { httpRequest } from "./client";

export interface GradingPoolDto {
  id: string;
  assessment_id: string;
  assessment_version_id: string;
  grading_mode: string;
  status: "DRAFT" | "ACTIVE" | "CLOSED";
  allocation_strategy: "MANUAL" | "ROUND_ROBIN";
  created_at: string;
  updated_at: string;
  member_count?: number;
}

export interface GradingWorkItemDto {
  id: string;
  pool_id: string;
  submission_id: string;
  evaluation_run_id: string;
  question_evaluation_id: string;
  assigned_evaluator_id: string;
  status: "QUEUED" | "IN_PROGRESS" | "SUBMITTED" | "RETURNED" | "COMPLETED";
  created_at: string;
  updated_at: string;
}

export interface ModerationCaseDto {
  id: string;
  policy_id: string;
  submission_id: string;
  evaluation_run_id: string;
  current_stage_order: number;
  status: "PENDING" | "IN_PROGRESS" | "APPROVED" | "RETURNED" | "REJECTED";
  created_at: string;
  updated_at: string;
  actions?: Array<{
    id: string;
    stage_order: number;
    actor_user_id: string;
    decision: "APPROVE" | "RETURN" | "REJECT";
    reason: string | null;
    created_at: string;
  }>;
}

export interface GrievanceCaseDto {
  id: string;
  submission_id: string;
  original_published_result_id: string;
  original_evaluation_run_id: string;
  requester_reference: string;
  submitted_by: string;
  reason: string;
  status: string;
  decision_reason: string | null;
  reevaluation_run_id: string | null;
  revised_published_result_id: string | null;
  created_at: string;
  updated_at: string;
}

export const OperationsHttpApi = {
  async listGradingPools() {
    return httpRequest<{ items: GradingPoolDto[] }>("/api/v1/operations/grading-pools");
  },
  async getGradingPool(poolId: string) {
    return httpRequest<GradingPoolDto>(`/api/v1/operations/grading-pools/${poolId}`);
  },
  async createGradingPool(input: {
    assessment_id: string;
    assessment_version_id: string;
    allocation_strategy: "MANUAL" | "ROUND_ROBIN";
  }) {
    return httpRequest<GradingPoolDto>("/api/v1/operations/grading-pools", {
      method: "POST",
      body: input,
    });
  },
  async activateGradingPool(poolId: string) {
    return httpRequest<GradingPoolDto>(
      `/api/v1/operations/grading-pools/${poolId}/activate`,
      { method: "POST" },
    );
  },
  async closeGradingPool(poolId: string) {
    return httpRequest<GradingPoolDto>(
      `/api/v1/operations/grading-pools/${poolId}/close`,
      { method: "POST" },
    );
  },
  async getGradingPoolProgress(poolId: string) {
    return httpRequest<{ counts: Record<string, number> }>(
      `/api/v1/operations/grading-pools/${poolId}/progress`,
    );
  },
  async myGradingQueue() {
    return httpRequest<{ items: GradingWorkItemDto[] }>(
      "/api/v1/operations/grading/my-queue",
    );
  },
  async startGradingWorkItem(workItemId: string) {
    return httpRequest<GradingWorkItemDto>(
      `/api/v1/operations/grading/work-items/${workItemId}/start`,
      { method: "POST" },
    );
  },
  async submitGradingWorkItem(workItemId: string) {
    return httpRequest<GradingWorkItemDto>(
      `/api/v1/operations/grading/work-items/${workItemId}/submit`,
      { method: "POST" },
    );
  },
  async listModerationCases() {
    return httpRequest<{ items: ModerationCaseDto[] }>(
      "/api/v1/operations/moderation-cases",
    );
  },
  async getModerationCase(caseId: string) {
    return httpRequest<ModerationCaseDto>(
      `/api/v1/operations/moderation-cases/${caseId}`,
    );
  },
  async decideModerationCase(
    caseId: string,
    input: { decision: "APPROVE" | "RETURN" | "REJECT"; reason?: string | null },
  ) {
    return httpRequest<ModerationCaseDto>(
      `/api/v1/operations/moderation-cases/${caseId}/decide`,
      { method: "POST", body: input },
    );
  },
  async listGrievances() {
    return httpRequest<{ items: GrievanceCaseDto[] }>("/api/v1/operations/grievances");
  },
  async getGrievance(id: string) {
    return httpRequest<GrievanceCaseDto>(`/api/v1/operations/grievances/${id}`);
  },
  async createGrievance(input: {
    published_result_id: string;
    requester_reference: string;
    reason: string;
  }) {
    return httpRequest<GrievanceCaseDto>("/api/v1/operations/grievances", {
      method: "POST",
      body: input,
    });
  },
  async acceptGrievance(id: string, decision_reason?: string | null) {
    return httpRequest<GrievanceCaseDto>(
      `/api/v1/operations/grievances/${id}/accept`,
      { method: "POST", body: { decision_reason: decision_reason ?? null } },
    );
  },
  async rejectGrievance(id: string, decision_reason: string) {
    return httpRequest<GrievanceCaseDto>(
      `/api/v1/operations/grievances/${id}/reject`,
      { method: "POST", body: { decision_reason } },
    );
  },
};
