import type {
  A2AnswerKeyVersion,
  A2Assessment,
  A2Curriculum,
  A2CurriculumMapping,
  A2CurriculumNode,
  A2QuestionVersion,
  A2RubricCriterion,
} from "@/lib/api/a2-types";
import type {
  AnswerKeyStep,
  Assessment,
  Curriculum,
  CurriculumMapEntry,
  CurriculumNode,
  Question,
  RubricCriterion,
} from "@/lib/types/domain";
import type { AssessmentState, CurriculumNodeType } from "@/lib/types/enums";

export interface AssessmentFormValues {
  curriculumId: string;
  code: string;
  title: string;
  assessmentType: string;
  maxMarks: number;
  durationMinutes?: number | null;
  academicYearId?: string | null;
  classSectionId?: string | null;
}

export function countCurriculumNodes(nodes: A2CurriculumNode[]): number {
  return nodes.reduce(
    (count, node) => count + 1 + countCurriculumNodes(node.children ?? []),
    0,
  );
}

export function curriculumApiToView(
  api: A2Curriculum,
  nodeCount = 0,
): Curriculum {
  return {
    id: api.id,
    tenant_id: api.tenant_id,
    code: api.code,
    title: api.name,
    board: api.academic_framework ?? "—",
    grade_label: api.version_label,
    subject: api.name,
    node_count: nodeCount,
    updated_at: api.updated_at ?? api.created_at ?? "",
  };
}

export function curriculumNodeApiToView(api: A2CurriculumNode): CurriculumNode {
  return {
    id: api.id,
    curriculum_id: api.curriculum_id,
    parent_id: api.parent_id,
    node_type: api.node_type as CurriculumNodeType,
    code: api.code,
    title: api.name,
    sort_order: api.sequence,
    metadata: api.metadata as CurriculumNode["metadata"],
    children: (api.children ?? []).map(curriculumNodeApiToView),
  };
}

export function assessmentApiToView(
  api: A2Assessment,
  curriculum?: A2Curriculum,
  questionCount = 0,
): Assessment {
  return {
    id: api.id,
    tenant_id: api.tenant_id,
    institution_id: "",
    title: api.title,
    code: api.code,
    subject: curriculum?.name ?? api.assessment_type,
    grade: curriculum?.version_label ?? "—",
    max_marks: Number(api.max_marks),
    workflow_state: api.status as AssessmentState,
    scheduled_at: null,
    question_count: questionCount,
    submission_count: 0,
    curriculum_id: api.curriculum_id,
    created_at: api.created_at ?? "",
    updated_at: api.updated_at ?? api.created_at ?? "",
  };
}

export function assessmentFormToApi(form: AssessmentFormValues) {
  return {
    curriculum_id: form.curriculumId,
    academic_year_id: form.academicYearId || null,
    class_section_id: form.classSectionId || null,
    subject_node_id: null,
    code: form.code.trim(),
    title: form.title.trim(),
    description: null,
    assessment_type: form.assessmentType.trim(),
    max_marks: form.maxMarks.toFixed(2),
    duration_minutes: form.durationMinutes ?? null,
  };
}

export function questionTreeApiToView(
  nodes: A2QuestionVersion[],
  assessmentId: string,
): Question[] {
  return nodes.map((node) => ({
    id: node.id,
    assessment_id: assessmentId,
    parent_id: node.parent_question_version_id,
    code: node.display_label,
    prompt: node.prompt_text,
    max_mark: Number(node.max_marks),
    sort_order: node.sequence,
    curriculum_node_ids: [],
    children: questionTreeApiToView(node.children ?? [], assessmentId),
  }));
}

export function flattenQuestionTree(nodes: A2QuestionVersion[]): A2QuestionVersion[] {
  return nodes.flatMap((node) => [node, ...flattenQuestionTree(node.children ?? [])]);
}

export function answerKeyApiToView(
  api: A2AnswerKeyVersion,
  marksByQuestion: Map<string, number>,
): AnswerKeyStep {
  return {
    id: api.id,
    question_id: api.question_version_id,
    step_index: 0,
    content: api.answer_text,
    marks: marksByQuestion.get(api.question_version_id) ?? 0,
  };
}

export function rubricCriterionApiToView(
  api: A2RubricCriterion,
  questionVersionId: string,
): RubricCriterion {
  return {
    id: api.id,
    question_id: questionVersionId,
    label: api.criterion_code,
    description: api.description,
    max_marks: Number(api.max_marks),
    sort_order: api.sequence,
  };
}

export function curriculumMappingsToView(
  question: A2QuestionVersion,
  mappings: A2CurriculumMapping[],
  nodeTitles: Map<string, string>,
): CurriculumMapEntry {
  return {
    question_id: question.id,
    question_code: question.display_label,
    curriculum_node_ids: mappings.map((mapping) => mapping.curriculum_node_id),
    node_titles: mappings.map(
      (mapping) => nodeTitles.get(mapping.curriculum_node_id) ?? mapping.curriculum_node_id,
    ),
  };
}

export function curriculumNodeTitleMap(nodes: A2CurriculumNode[]): Map<string, string> {
  const result = new Map<string, string>();
  const visit = (items: A2CurriculumNode[]) => {
    for (const node of items) {
      result.set(node.id, node.name);
      visit(node.children ?? []);
    }
  };
  visit(nodes);
  return result;
}
