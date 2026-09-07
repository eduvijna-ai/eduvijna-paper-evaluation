import type {
  Assessment,
  ParentReport,
  Student,
  StudentReport,
  TeacherReport,
} from "@/lib/types/domain";
import type { EvaluationWorkflowState, ErrorCode } from "@/lib/types/enums";
import { httpRequest } from "./client";

function asNumber(value: number | string | null | undefined, fallback = 0): number {
  if (value === null || value === undefined || value === "") return fallback;
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n : fallback;
}

/** Live B7 student audience report DTO (contracts/schemas/student-report.schema.json). */
export interface B7StudentReportDto {
  published_result_id: string;
  student: { id: string; display_name: string };
  assessment: {
    id: string;
    title: string;
    code?: string;
    assessment_version_id: string;
  };
  total_score: number | string;
  max_total_score: number | string;
  percentage: number | string;
  questions: Array<{
    question_id: string;
    question_version_id?: string;
    question_code: string;
    final_score: number | string;
    max_mark: number | string;
    feedback?: string | null;
    error_explanations?: string[];
    corrected_approach?: string | null;
    explanation?: string | null;
  }>;
  strengths: string[];
  areas_for_improvement: string[];
  next_steps: string[];
  ledger_snapshot_hash: string;
  narrative_source: "AI" | "FIXED" | "RULES_FALLBACK";
  evaluation_run_id?: string;
  generated_at?: string;
  published_at?: string | null;
}

/** Live B7 parent audience report DTO. */
export interface B7ParentReportDto {
  published_result_id: string;
  student_display_name: string;
  assessment_title: string;
  total_score: number | string;
  max_total_score: number | string;
  percentage: number | string;
  score_summary?: string;
  what_went_well: string[];
  what_to_practice: string[];
  how_family_can_help: string[];
  next_step: string;
  ledger_snapshot_hash: string;
  narrative_source: "AI" | "FIXED" | "RULES_FALLBACK";
  generated_at?: string;
  published_at?: string | null;
}

/** Live B7 teacher diagnostic report DTO. */
export interface B7TeacherReportDto {
  published_result_id: string;
  student: { id: string; display_name: string };
  assessment: {
    id: string;
    title: string;
    code?: string;
    assessment_version_id: string;
  };
  total_score: number | string;
  max_total_score: number | string;
  questions: Array<{
    question_id: string;
    question_version_id?: string;
    question_code: string;
    final_score: number | string;
    max_mark: number | string;
    workflow_state: string;
    criterion_decisions: Array<Record<string, unknown>>;
    error_codes: string[];
    deduction_reasons?: string[];
    first_divergence_step?: number | null;
    ecf_applied?: boolean;
    alternative_method_label?: string | null;
    confidences?: TeacherReport["questions"][number]["confidences"];
  }>;
  ledger_snapshot_hash: string;
  evaluation_run_id?: string;
  generated_at?: string;
  published_at?: string | null;
}

function stubStudent(id: string, displayName: string): Student {
  const parts = displayName.trim().split(/\s+/);
  const first = parts[0] ?? displayName;
  const last = parts.slice(1).join(" ") || "";
  return {
    id,
    tenant_id: "",
    institution_id: "",
    class_section_id: "",
    external_ref: id.slice(0, 8),
    first_name: first,
    last_name: last,
    display_name: displayName,
    grade: "",
    section: "",
    status: "ACTIVE",
  };
}

function stubAssessment(
  id: string,
  title: string,
  code: string | undefined,
  maxMarks: number,
): Assessment {
  const now = new Date().toISOString();
  return {
    id,
    tenant_id: "",
    institution_id: "",
    title,
    code: code ?? id.slice(0, 8),
    subject: "",
    grade: "",
    max_marks: maxMarks,
    workflow_state: "READY",
    scheduled_at: null,
    question_count: 0,
    submission_count: 0,
    curriculum_id: "",
    created_at: now,
    updated_at: now,
  };
}

/** Map live student report → domain StudentReport. Never uses proposed scores. */
export function studentReportApiToView(dto: B7StudentReportDto): StudentReport {
  const maxMarks = asNumber(dto.max_total_score);
  const total = asNumber(dto.total_score);
  return {
    student: stubStudent(dto.student.id, dto.student.display_name),
    assessment: stubAssessment(
      dto.assessment.id,
      dto.assessment.title,
      dto.assessment.code,
      maxMarks,
    ),
    total_score: total,
    max_marks: maxMarks,
    percentage: asNumber(dto.percentage),
    question_summaries: (dto.questions ?? []).map((q) => {
      const finalScore = asNumber(q.final_score);
      return {
        question_id: q.question_id,
        question_code: q.question_code,
        max_mark: asNumber(q.max_mark),
        // Live publication never surfaces proposed_ai_score — mirror final only.
        proposed_score: finalScore,
        final_score: finalScore,
        workflow_state: "ACCEPTED" as EvaluationWorkflowState,
        error_codes: [] as ErrorCode[],
      };
    }),
    strengths: dto.strengths ?? [],
    weaknesses: dto.areas_for_improvement ?? [],
    patterns: [],
    next_actions: dto.next_steps ?? [],
    // B7 does not fabricate mastery topics — UI hides Topics when live_published.
    topic_focus: [],
    evidence_highlights: (dto.questions ?? []).flatMap((q) => {
      const explanation = q.explanation ?? q.feedback;
      if (!explanation) return [];
      const final = asNumber(q.final_score);
      const max = asNumber(q.max_mark);
      const outcome =
        final >= max && max > 0
          ? ("CORRECT" as const)
          : final <= 0
            ? ("DEDUCTED" as const)
            : ("PARTIAL" as const);
      return [
        {
          question_code: q.question_code,
          excerpt: explanation,
          outcome,
        },
      ];
    }),
    corrected_approaches: (dto.questions ?? [])
      .filter((q) => q.corrected_approach)
      .map((q) => ({
        question_code: q.question_code,
        approach: q.corrected_approach as string,
      })),
    live_published: true,
    ledger_snapshot_hash: dto.ledger_snapshot_hash,
    narrative_source: dto.narrative_source,
    published_result_id: dto.published_result_id,
  };
}

export function parentReportApiToView(dto: B7ParentReportDto): ParentReport {
  const total = asNumber(dto.total_score);
  const max = asNumber(dto.max_total_score);
  const percentage = asNumber(dto.percentage);
  return {
    student_display_name: dto.student_display_name,
    assessment_title: dto.assessment_title,
    score_summary:
      dto.score_summary ??
      `${dto.student_display_name} scored ${total} of ${max} (${percentage}%).`,
    what_went_well: dto.what_went_well ?? [],
    what_to_practice: dto.what_to_practice ?? [],
    how_to_help: dto.how_family_can_help ?? [],
    next_step: dto.next_step,
    total_score: total,
    max_total_score: max,
    percentage,
    live_published: true,
    ledger_snapshot_hash: dto.ledger_snapshot_hash,
    narrative_source: dto.narrative_source,
    published_result_id: dto.published_result_id,
  };
}

export function teacherReportApiToView(dto: B7TeacherReportDto): TeacherReport {
  return {
    published_result_id: dto.published_result_id,
    student: dto.student,
    assessment: dto.assessment,
    total_score: asNumber(dto.total_score),
    max_total_score: asNumber(dto.max_total_score),
    questions: (dto.questions ?? []).map((q) => ({
      question_id: q.question_id,
      question_version_id: q.question_version_id,
      question_code: q.question_code,
      final_score: asNumber(q.final_score),
      max_mark: asNumber(q.max_mark),
      workflow_state: q.workflow_state,
      criterion_decisions: q.criterion_decisions ?? [],
      error_codes: q.error_codes ?? [],
      deduction_reasons: q.deduction_reasons,
      first_divergence_step: q.first_divergence_step,
      ecf_applied: q.ecf_applied,
      alternative_method_label: q.alternative_method_label,
      confidences: q.confidences,
    })),
    ledger_snapshot_hash: dto.ledger_snapshot_hash,
    evaluation_run_id: dto.evaluation_run_id,
    generated_at: dto.generated_at,
    published_at: dto.published_at,
  };
}

/**
 * Live B7 published audience report resolvers.
 * Only returns PUBLISHED payloads (backend 404 otherwise).
 */
export const ReportsHttpApi = {
  async getStudentReport(
    studentId: string,
    assessmentId: string,
  ): Promise<StudentReport> {
    const dto = await httpRequest<B7StudentReportDto>(
      `/api/v1/reports/student/${studentId}/assessments/${assessmentId}`,
    );
    return studentReportApiToView(dto);
  },

  async getParentReport(
    studentId: string,
    assessmentId: string,
  ): Promise<ParentReport> {
    const dto = await httpRequest<B7ParentReportDto>(
      `/api/v1/reports/parent/${studentId}/assessments/${assessmentId}`,
    );
    return parentReportApiToView(dto);
  },

  async getTeacherReport(
    studentId: string,
    assessmentId: string,
  ): Promise<TeacherReport> {
    const dto = await httpRequest<B7TeacherReportDto>(
      `/api/v1/reports/teacher/${studentId}/assessments/${assessmentId}`,
    );
    return teacherReportApiToView(dto);
  },
};
