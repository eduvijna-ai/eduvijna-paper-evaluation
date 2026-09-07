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
import type {
  AssessmentArtifact,
  AuthoringAiRun,
  ProposedQuestionNode,
} from "@/lib/types/domain";
import { httpRequest } from "./client";
import { isApiError } from "./errors";

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

function asId(value: unknown): string {
  return String(value ?? "");
}

function authoringRunApiToView(raw: Record<string, unknown>): AuthoringAiRun {
  return {
    id: asId(raw.id),
    tenant_id: asId(raw.tenant_id),
    assessment_id: asId(raw.assessment_id),
    assessment_version_id: asId(raw.assessment_version_id),
    question_version_id: raw.question_version_id
      ? asId(raw.question_version_id)
      : null,
    assessment_artifact_id: raw.assessment_artifact_id
      ? asId(raw.assessment_artifact_id)
      : null,
    operation: String(raw.operation ?? ""),
    status: String(raw.status ?? ""),
    input_hash: String(raw.input_hash ?? ""),
    proposal_payload: (raw.proposal_payload as AuthoringAiRun["proposal_payload"]) ?? null,
    requested_by: asId(raw.requested_by),
    requested_at: raw.requested_at ? String(raw.requested_at) : null,
    started_at: raw.started_at ? String(raw.started_at) : null,
    finished_at: raw.finished_at ? String(raw.finished_at) : null,
    celery_task_id: raw.celery_task_id ? String(raw.celery_task_id) : null,
    answer_key_version_id: raw.answer_key_version_id
      ? asId(raw.answer_key_version_id)
      : null,
    rubric_version_id: raw.rubric_version_id
      ? asId(raw.rubric_version_id)
      : null,
    correlation_id: raw.correlation_id ? String(raw.correlation_id) : null,
    failure_code: raw.failure_code ? String(raw.failure_code) : null,
    failure_detail: raw.failure_detail ? String(raw.failure_detail) : null,
    enqueue_error: raw.enqueue_error ? String(raw.enqueue_error) : null,
  };
}

function artifactApiToView(raw: Record<string, unknown>): AssessmentArtifact {
  return {
    id: asId(raw.id),
    tenant_id: asId(raw.tenant_id),
    assessment_id: asId(raw.assessment_id),
    artifact_type: String(raw.artifact_type ?? "QUESTION_PAPER"),
    original_filename: String(raw.original_filename ?? ""),
    mime_type: String(raw.mime_type ?? ""),
    byte_size: Number(raw.byte_size ?? 0),
    content_sha256: String(raw.content_sha256 ?? ""),
    storage_key: String(raw.storage_key ?? ""),
    security_scan_status: String(raw.security_scan_status ?? "NOT_CONFIGURED"),
    uploaded_by: raw.uploaded_by ? asId(raw.uploaded_by) : null,
    uploaded_at: String(raw.uploaded_at ?? ""),
    created_at: raw.created_at ? String(raw.created_at) : null,
  };
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

  async getLatestAssessmentVersion(assessmentId: string) {
    const version = latestVersion(await listVersions(assessmentId));
    if (!version) {
      throw new Error("Assessment has no version");
    }
    return version;
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
        return rows.map((row) =>
          rubricCriterionApiToView(row, latest.question_version_id, {
            id: latest.id,
            source_type: latest.source_type,
            status: latest.status,
          }),
        );
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

  async uploadQuestionPaper(versionId: string, file: File): Promise<AssessmentArtifact> {
    const form = new FormData();
    form.append("file", file, file.name);
    const row = await httpRequest<Record<string, unknown>>(
      `/api/v1/assessment-versions/${versionId}/question-paper`,
      { method: "POST", formData: form },
    );
    return artifactApiToView(row);
  },

  async prepareQuestionPaperParse(versionId: string): Promise<AuthoringAiRun> {
    const row = await httpRequest<Record<string, unknown>>(
      `/api/v1/assessment-versions/${versionId}/question-paper/parse`,
      { method: "POST" },
    );
    return authoringRunApiToView(row);
  },

  async getLatestAuthoringAiRun(
    versionId: string,
    operation?: string,
  ): Promise<AuthoringAiRun | null> {
    const query = operation
      ? `?operation=${encodeURIComponent(operation)}`
      : "";
    try {
      const row = await httpRequest<Record<string, unknown>>(
        `/api/v1/assessment-versions/${versionId}/authoring-ai-runs/latest${query}`,
      );
      return authoringRunApiToView(row);
    } catch (err) {
      if (isApiError(err) && err.status === 404) return null;
      throw err;
    }
  },

  async getAssessmentArtifact(artifactId: string): Promise<AssessmentArtifact> {
    const row = await httpRequest<Record<string, unknown>>(
      `/api/v1/assessment-artifacts/${artifactId}`,
    );
    return artifactApiToView(row);
  },

  async getAuthoringAiRun(runId: string): Promise<AuthoringAiRun> {
    const row = await httpRequest<Record<string, unknown>>(
      `/api/v1/authoring-ai-runs/${runId}`,
    );
    return authoringRunApiToView(row);
  },

  async updateQuestionTreeProposal(
    runId: string,
    tree: { roots: ProposedQuestionNode[]; notes?: string | null },
  ): Promise<AuthoringAiRun> {
    const row = await httpRequest<Record<string, unknown>>(
      `/api/v1/authoring-ai-runs/${runId}/question-tree-proposal`,
      {
        method: "PUT",
        body: {
          roots: tree.roots,
          notes: tree.notes ?? null,
        },
      },
    );
    return authoringRunApiToView(row);
  },

  async applyQuestionTreeProposal(runId: string): Promise<AuthoringAiRun> {
    const row = await httpRequest<Record<string, unknown>>(
      `/api/v1/authoring-ai-runs/${runId}/apply-question-tree`,
      { method: "POST" },
    );
    return authoringRunApiToView(row);
  },

  async createTeacherAnswerKey(input: {
    assessmentId: string;
    assessmentVersionId: string;
    questionVersionId: string;
    answerText: string;
  }) {
    return httpRequest<A2AnswerKeyVersion>(
      `/api/v1/assessments/${input.assessmentId}/answer-key-versions`,
      {
        method: "POST",
        body: {
          assessment_version_id: input.assessmentVersionId,
          question_version_id: input.questionVersionId,
          answer_text: input.answerText,
          source_type: "TEACHER",
          status: "DRAFT",
        },
      },
    );
  },

  async updateAnswerKey(
    answerKeyVersionId: string,
    patch: { answerText?: string; status?: "DRAFT" | "REVIEW_REQUIRED" },
  ) {
    return httpRequest<A2AnswerKeyVersion>(
      `/api/v1/answer-key-versions/${answerKeyVersionId}`,
      {
        method: "PATCH",
        body: {
          ...(patch.answerText !== undefined
            ? { answer_text: patch.answerText }
            : {}),
          ...(patch.status !== undefined ? { status: patch.status } : {}),
        },
      },
    );
  },

  async approveAnswerKey(answerKeyVersionId: string) {
    return httpRequest<A2AnswerKeyVersion>(
      `/api/v1/answer-key-versions/${answerKeyVersionId}/approve`,
      { method: "POST" },
    );
  },

  async prepareAiAnswerKeyProposal(input: {
    questionVersionId: string;
    assessmentVersionId?: string;
    instructions?: string;
  }): Promise<AuthoringAiRun> {
    const row = await httpRequest<Record<string, unknown>>(
      "/api/v1/ai/proposals/answer-key",
      {
        method: "POST",
        body: {
          question_version_id: input.questionVersionId,
          ...(input.assessmentVersionId
            ? { assessment_version_id: input.assessmentVersionId }
            : {}),
          ...(input.instructions ? { instructions: input.instructions } : {}),
        },
      },
    );
    return authoringRunApiToView(row);
  },

  async createTeacherRubric(input: {
    assessmentId: string;
    questionVersionId: string;
    title: string;
    criteria: Array<{
      criterionCode: string;
      description: string;
      maxMarks: number | string;
      sequence: number;
      scoringMode?: "ADDITIVE" | "DEDUCTIVE" | "ALL_OR_NOTHING";
      partialCreditAllowed?: boolean;
    }>;
  }) {
    const rubric = await httpRequest<A2Rubric>(
      `/api/v1/assessments/${input.assessmentId}/rubrics`,
      {
        method: "POST",
        body: {
          question_version_id: input.questionVersionId,
          title: input.title,
          provenance: "TEACHER",
        },
      },
    );
    const version = await httpRequest<A2RubricVersion>(
      `/api/v1/rubrics/${rubric.id}/versions`,
      {
        method: "POST",
        body: {
          question_version_id: input.questionVersionId,
          source_type: "TEACHER",
          status: "DRAFT",
        },
      },
    );
    const criteria = [];
    for (const criterion of input.criteria) {
      const created = await httpRequest<A2RubricCriterion>(
        `/api/v1/rubric-versions/${version.id}/criteria`,
        {
          method: "POST",
          body: {
            criterion_code: criterion.criterionCode,
            description: criterion.description,
            max_marks:
              typeof criterion.maxMarks === "number"
                ? criterion.maxMarks.toFixed(2)
                : criterion.maxMarks,
            sequence: criterion.sequence,
            scoring_mode: criterion.scoringMode ?? "ADDITIVE",
            partial_credit_allowed: criterion.partialCreditAllowed ?? false,
            ecf_policy: "NONE",
          },
        },
      );
      criteria.push(created);
    }
    return { rubric, version, criteria };
  },

  async updateRubric(
    rubricVersionId: string,
    patch: {
      questionVersionId: string;
      status?: "DRAFT" | "REVIEW_REQUIRED";
      sourceType?: "TEACHER" | "IMPORTED";
    },
  ) {
    return httpRequest<A2RubricVersion>(
      `/api/v1/rubric-versions/${rubricVersionId}`,
      {
        method: "PATCH",
        body: {
          question_version_id: patch.questionVersionId,
          source_type: patch.sourceType ?? "TEACHER",
          status: patch.status ?? "DRAFT",
        },
      },
    );
  },

  async approveRubric(rubricVersionId: string) {
    return httpRequest<A2RubricVersion>(
      `/api/v1/rubric-versions/${rubricVersionId}/approve`,
      { method: "POST" },
    );
  },

  async prepareAiRubricProposal(input: {
    questionVersionId: string;
    assessmentVersionId?: string;
    instructions?: string;
  }): Promise<AuthoringAiRun> {
    const row = await httpRequest<Record<string, unknown>>(
      "/api/v1/ai/proposals/rubric",
      {
        method: "POST",
        body: {
          question_version_id: input.questionVersionId,
          ...(input.assessmentVersionId
            ? { assessment_version_id: input.assessmentVersionId }
            : {}),
          ...(input.instructions ? { instructions: input.instructions } : {}),
        },
      },
    );
    return authoringRunApiToView(row);
  },

  async prepareAiCurriculumMappingProposal(input: {
    questionVersionId: string;
    curriculumId?: string;
    instructions?: string;
  }): Promise<AuthoringAiRun> {
    const row = await httpRequest<Record<string, unknown>>(
      "/api/v1/ai/proposals/curriculum-mapping",
      {
        method: "POST",
        body: {
          question_version_id: input.questionVersionId,
          ...(input.curriculumId ? { curriculum_id: input.curriculumId } : {}),
          ...(input.instructions ? { instructions: input.instructions } : {}),
          context: {},
        },
      },
    );
    return authoringRunApiToView(row);
  },

  async updateCurriculumMappingProposal(
    runId: string,
    mappings: Array<{
      curriculum_node_id: string;
      mapping_type: "PRIMARY" | "SECONDARY" | "LEARNING_OUTCOME" | "SKILL";
      weight?: string | number | null;
      rationale?: string | null;
    }>,
  ): Promise<AuthoringAiRun> {
    const row = await httpRequest<Record<string, unknown>>(
      `/api/v1/authoring-ai-runs/${runId}/curriculum-mapping-proposal`,
      {
        method: "PUT",
        body: { mappings },
      },
    );
    return authoringRunApiToView(row);
  },

  async applyCurriculumMappings(
    runId: string,
    selectedIndices?: number[] | null,
  ): Promise<AuthoringAiRun> {
    const row = await httpRequest<Record<string, unknown>>(
      `/api/v1/authoring-ai-runs/${runId}/apply-curriculum-mappings`,
      {
        method: "POST",
        body: {
          selected_indices:
            selectedIndices === undefined ? null : selectedIndices,
        },
      },
    );
    return authoringRunApiToView(row);
  },

  async transitionAssessment(assessmentId: string, toStatus: string) {
    return httpRequest<A2Assessment>(
      `/api/v1/assessments/${assessmentId}/transition`,
      {
        method: "POST",
        body: { to_status: toStatus },
      },
    );
  },
};
