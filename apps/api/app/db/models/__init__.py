from app.db.models.academic import AcademicYear, ClassSection
from app.db.models.ai_structure import (
    AnswerRegionTranscription,
    SubmissionIdentityCandidate,
    SubmissionPageAnalysis,
)
from app.db.models.audit import AuditEvent
from app.db.models.authoring import AssessmentArtifact, AuthoringAiRun
from app.db.models.curriculum_assessment import (
    AiExecutionRecord,
    AnswerKey,
    AnswerKeyVersion,
    Assessment,
    AssessmentVersion,
    Curriculum,
    CurriculumNode,
    CurriculumPrerequisite,
    Question,
    QuestionCurriculumMapping,
    QuestionVersion,
    Rubric,
    RubricCriterion,
    RubricVersion,
)
from app.db.models.evaluation import (
    CriterionEvaluation,
    EvaluationRun,
    QuestionEvaluation,
    ReviewAction,
)
from app.db.models.institution import Institution
from app.db.models.learning import (
    ImprovementAssessment,
    ImprovementAssessmentItem,
    LearningPathStep,
    LearningPlanRun,
    LearningRecommendation,
    LearningRecommendationEvidence,
    LearningRecommendationPrerequisite,
)
from app.db.models.mapping import (
    AnswerRegion,
    QuestionAnswerMapping,
    QuestionAnswerMappingRegion,
)
from app.db.models.mastery import MasteryEvidence
from app.db.models.publication import Annotation, PublishedResult
from app.db.models.role import Permission, Role, RolePermission, UserRole
from app.db.models.student import Guardian, ImportSession, Student, StudentGuardian
from app.db.models.submission import PipelineJob, Submission, SubmissionPage
from app.db.models.tenant import Tenant
from app.db.models.user import User

__all__ = [
    "AcademicYear",
    "AiExecutionRecord",
    "Annotation",
    "AnswerKey",
    "AnswerKeyVersion",
    "AnswerRegion",
    "AnswerRegionTranscription",
    "Assessment",
    "AssessmentArtifact",
    "AssessmentVersion",
    "AuditEvent",
    "AuthoringAiRun",
    "ClassSection",
    "CriterionEvaluation",
    "Curriculum",
    "CurriculumNode",
    "CurriculumPrerequisite",
    "EvaluationRun",
    "Guardian",
    "ImprovementAssessment",
    "ImprovementAssessmentItem",
    "Institution",
    "ImportSession",
    "LearningPathStep",
    "LearningPlanRun",
    "LearningRecommendation",
    "LearningRecommendationEvidence",
    "LearningRecommendationPrerequisite",
    "MasteryEvidence",
    "Permission",
    "PipelineJob",
    "PublishedResult",
    "Question",
    "QuestionAnswerMapping",
    "QuestionAnswerMappingRegion",
    "QuestionCurriculumMapping",
    "QuestionEvaluation",
    "QuestionVersion",
    "ReviewAction",
    "Role",
    "RolePermission",
    "Rubric",
    "RubricCriterion",
    "RubricVersion",
    "Student",
    "StudentGuardian",
    "Submission",
    "SubmissionIdentityCandidate",
    "SubmissionPage",
    "SubmissionPageAnalysis",
    "Tenant",
    "User",
    "UserRole",
]
