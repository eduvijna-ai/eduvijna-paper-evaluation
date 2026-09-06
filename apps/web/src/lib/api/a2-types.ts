/** A2 curriculum/assessment transport types. Keep snake_case at the HTTP boundary. */

export interface A2Curriculum {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  description?: string | null;
  academic_framework?: string | null;
  version_label: string;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface A2CurriculumNode {
  id: string;
  tenant_id: string;
  curriculum_id: string;
  parent_id: string | null;
  node_type: string;
  code: string;
  name: string;
  description?: string | null;
  sequence: number;
  metadata?: Record<string, unknown>;
  status: string;
  created_at?: string;
  updated_at?: string;
  children?: A2CurriculumNode[];
}

export interface A2Assessment {
  id: string;
  tenant_id: string;
  academic_year_id?: string | null;
  class_section_id?: string | null;
  curriculum_id: string;
  subject_node_id?: string | null;
  code: string;
  title: string;
  description?: string | null;
  assessment_type: string;
  max_marks: string | number;
  duration_minutes?: number | null;
  status: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
  initial_version_id?: string;
}

export interface A2AssessmentVersion {
  id: string;
  tenant_id: string;
  assessment_id: string;
  version_number: number;
  title: string;
  instructions?: string | null;
  max_marks: string | number;
  question_paper_artifact_id?: string | null;
  status: string;
  created_at?: string;
  updated_at?: string;
}

export interface A2QuestionVersion {
  id: string;
  tenant_id: string;
  assessment_version_id: string;
  question_id: string;
  parent_question_version_id: string | null;
  display_label: string;
  sequence: number;
  prompt_text: string;
  max_marks: string | number;
  question_type: string;
  scoring_mode: string;
  instructions?: string | null;
  children?: A2QuestionVersion[];
}

export interface A2AnswerKeyVersion {
  id: string;
  tenant_id: string;
  answer_key_id: string;
  assessment_version_id: string;
  question_version_id: string;
  version_number: number;
  answer_text: string;
  structured_answer?: Record<string, unknown> | null;
  source_type: string;
  status: string;
}

export interface A2Rubric {
  id: string;
  tenant_id: string;
  assessment_id: string;
  question_version_id: string | null;
  title: string;
  provenance: string;
}

export interface A2RubricVersion {
  id: string;
  tenant_id: string;
  rubric_id: string;
  question_version_id: string;
  version_number: number;
  status: string;
  source_type: string;
  approved_by?: string | null;
  approved_at?: string | null;
}

export interface A2RubricCriterion {
  id: string;
  tenant_id: string;
  rubric_version_id: string;
  criterion_code: string;
  description: string;
  max_marks: string | number;
  sequence: number;
  scoring_mode: string;
  partial_credit_allowed: boolean;
  ecf_policy: string;
}

export interface A2CurriculumMapping {
  id: string;
  tenant_id: string;
  question_version_id: string;
  curriculum_node_id: string;
  mapping_type: string;
  weight?: string | number | null;
}

export const A2_PERMISSIONS = {
  curriculumRead: "curriculum:read",
  curriculumManage: "curriculum:manage",
  assessmentRead: "assessment:read",
  assessmentManage: "assessment:manage",
  assessmentApprove: "assessment:approve",
  rubricRead: "rubric:read",
  rubricManage: "rubric:manage",
  rubricApprove: "rubric:approve",
} as const;
