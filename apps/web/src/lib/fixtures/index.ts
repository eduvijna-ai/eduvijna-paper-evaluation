/**
 * Fixture re-exports for tests and mock-adapter internals only.
 * Pages and UI components MUST use `@/lib/api` methods — never import fixtures directly.
 */
export {
  assessments,
  students,
  submissions,
  rubrics,
  answerKeys,
  paperPages,
  evidenceRegions,
  evaluationLedgers,
  curricula,
  curriculumNodes,
  questions,
  getDashboardSummary,
  getIdentityReview,
  getMappingReview,
  getEvaluationWorkspace,
  getStudentReport,
  getParentReport,
  getAssessmentAnalytics,
  getStudentAnalytics,
  getAdaptiveLearning,
  getImprovementBlueprint,
  getAssessmentCurriculumMap,
  buildCurriculumTree,
  buildQuestionTree,
} from "@/lib/api/mock/data";
