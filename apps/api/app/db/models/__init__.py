from app.db.models.academic import AcademicYear, ClassSection
from app.db.models.audit import AuditEvent
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
from app.db.models.institution import Institution
from app.db.models.mapping import (
    AnswerRegion,
    QuestionAnswerMapping,
    QuestionAnswerMappingRegion,
)
from app.db.models.role import Permission, Role, RolePermission, UserRole
from app.db.models.student import Guardian, ImportSession, Student, StudentGuardian
from app.db.models.submission import PipelineJob, Submission, SubmissionPage
from app.db.models.tenant import Tenant
from app.db.models.user import User

__all__ = [
    "AcademicYear",
    "AiExecutionRecord",
    "AnswerKey",
    "AnswerKeyVersion",
    "AnswerRegion",
    "Assessment",
    "AssessmentVersion",
    "AuditEvent",
    "ClassSection",
    "Curriculum",
    "CurriculumNode",
    "CurriculumPrerequisite",
    "Guardian",
    "Institution",
    "ImportSession",
    "Permission",
    "PipelineJob",
    "Question",
    "QuestionAnswerMapping",
    "QuestionAnswerMappingRegion",
    "QuestionCurriculumMapping",
    "QuestionVersion",
    "Role",
    "RolePermission",
    "Rubric",
    "RubricCriterion",
    "RubricVersion",
    "Student",
    "StudentGuardian",
    "Submission",
    "SubmissionPage",
    "Tenant",
    "User",
    "UserRole",
]
