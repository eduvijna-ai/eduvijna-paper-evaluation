import type {
  A2AnswerKeyVersion,
  A2Assessment,
  A2AssessmentVersion,
  A2Curriculum,
  A2CurriculumMapping,
  A2CurriculumNode,
  A2QuestionVersion,
  A2Rubric,
  A2RubricCriterion,
  A2RubricVersion,
} from "@/lib/api/a2-types";
import {
  answerKeyApiToView,
  assessmentApiToView,
  assessmentFormToApi,
  countCurriculumNodes,
  curriculumApiToView,
  curriculumMappingsToView,
  curriculumNodeApiToView,
  curriculumNodeTitleMap,
  flattenQuestionTree,
  questionTreeApiToView,
  rubricCriterionApiToView,
  type AssessmentFormValues,
} from "@/lib/api/mappers/authoring";
import { httpRequest } from "./client";

function latestVersion(versions: A2AssessmentVersion[]): A2AssessmentVersion | undefined {
  return [...versions].sort((a, b) => b.version_number - a.version_number)[0];
}

function latestByQuestion<T extends { question_version_id: string; version_number: number }>(
  items: T[],
): T[] {
  const latest = new Map<string, T>();
  for (const item of items) {
    const current = latest.get(item.question_version_id);
    if (!current || item.version_number > current.version_number) {
      latest.set(item.question_version_id, item);
    }
  }
  return [...latest.values()];
}

async function listVersions(assessmentId: string): Promise<A2AssessmentVersion[]> {
  return httpRequest<A2AssessmentVersion[]>(`/api/v1/assessments/${assessmentId}/versions`);
}

async function latestQuestionTree(
  assessmentId: string,
): Promise<{ version?: A2AssessmentVersion; tree: A2QuestionVersion[] }> {
  const version = latestVersion(await listVersions(assessmentId));
  if (!version) return { tree: [] };
  const tree = await httpRequest<A2QuestionVersion[]>(
    `/api/v1/assessment-versions/${version.id}/questions`,
  );
  return { version, tree };
}

async function curriculumLookup(): Promise<Map<string, A2Curriculum>> {
  const curricula = await httpRequest<A2Curriculum[]>("/api/v1/curricula");
  return new Map(curricula.map((curriculum) => [curriculum.id, curriculum]));
}

export const AuthoringHttpApi = {
  async listCurricula() {
    const rows = await httpRequest<A2Curriculum[]>("/api/v1/curricula");
    return Promise.all(
      rows.map(async (row) => {
        const tree = await httpRequest<A2CurriculumNode[]>(
          `/api/v1/curricula/${row.id}/tree`,
        );
        return curriculumApiToView(row, countCurriculumNodes(tree));
      }),
    );
  },

  async getCurriculum(id: string) {
    const [curriculum, tree] = await Promise.all([
      httpRequest<A2Curriculum>(`/api/v1/curricula/${id}`),
      httpRequest<A2CurriculumNode[]>(`/api/v1/curricula/${id}/tree`),
    ]);
    return {
      curriculum: curriculumApiToView(curriculum, countCurriculumNodes(tree)),
      tree: tree.map(curriculumNodeApiToView),
    };
  },

  async listAssessments() {
    const [rows, curricula] = await Promise.all([
      httpRequest<A2Assessment[]>("/api/v1/assessments"),
      curriculumLookup(),
    ]);
    return rows.map((row) => assessmentApiToView(row, curricula.get(row.curriculum_id)));
  },

  async getAssessment(id: string) {
    const [assessment, curricula, questionState] = await Promise.all([
      httpRequest<A2Assessment>(`/api/v1/assessments/${id}`),
      curriculumLookup(),
      latestQuestionTree(id),
    ]);
    const count = flattenQuestionTree(questionState.tree).length;
    return assessmentApiToView(assessment, curricula.get(assessment.curriculum_id), count);
  },

  async createAssessment(form: AssessmentFormValues) {
    const created = await httpRequest<A2Assessment>("/api/v1/assessments", {
      method: "POST",
      body: assessmentFormToApi(form),
    });
    const curriculum = await httpRequest<A2Curriculum>(
      `/api/v1/curricula/${created.curriculum_id}`,
    );
    return assessmentApiToView(created, curriculum, 0);
  },

  async getAssessmentQuestions(id: string) {
    const { tree } = await latestQuestionTree(id);
    return questionTreeApiToView(tree, id);
  },

  async getAssessmentAnswerKey(id: string) {
    const [{ tree }, versions] = await Promise.all([
      latestQuestionTree(id),
      httpRequest<A2AnswerKeyVersion[]>(
        `/api/v1/assessments/${id}/answer-key-versions`,
      ),
    ]);
    const questions = flattenQuestionTree(tree);
    const marks = new Map(questions.map((question) => [question.id, Number(question.max_marks)]));
    return latestByQuestion(versions)
      .sort((a, b) => a.question_version_id.localeCompare(b.question_version_id))
      .map((version) => answerKeyApiToView(version, marks));
  },

  async getAssessmentRubric(id: string) {
    const rubrics = await httpRequest<A2Rubric[]>(`/api/v1/assessments/${id}/rubrics`);
    const criteria = await Promise.all(
      rubrics.map(async (rubric) => {
        const versions = await httpRequest<A2RubricVersion[]>(
          `/api/v1/rubrics/${rubric.id}/versions`,
        );
        const latest = [...versions].sort((a, b) => b.version_number - a.version_number)[0];
        if (!latest) return [];
        const rows = await httpRequest<A2RubricCriterion[]>(
          `/api/v1/rubric-versions/${latest.id}/criteria`,
        );
        return rows.map((row) => rubricCriterionApiToView(row, latest.question_version_id));
      }),
    );
    return criteria.flat().sort((a, b) => a.sort_order - b.sort_order);
  },

  async getAssessmentCurriculumMap(id: string) {
    const [assessment, questionState] = await Promise.all([
      httpRequest<A2Assessment>(`/api/v1/assessments/${id}`),
      latestQuestionTree(id),
    ]);
    const [curriculumTree, mappings] = await Promise.all([
      httpRequest<A2CurriculumNode[]>(
        `/api/v1/curricula/${assessment.curriculum_id}/tree`,
      ),
      Promise.all(
        flattenQuestionTree(questionState.tree).map((question) =>
          httpRequest<A2CurriculumMapping[]>(
            `/api/v1/question-versions/${question.id}/curriculum-mappings`,
          ),
        ),
      ),
    ]);
    const questions = flattenQuestionTree(questionState.tree);
    const nodeTitles = curriculumNodeTitleMap(curriculumTree);
    return questions.map((question, index) =>
      curriculumMappingsToView(question, mappings[index] ?? [], nodeTitles),
    );
  },
};
