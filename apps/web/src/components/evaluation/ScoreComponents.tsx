import { cn } from "@/lib/utils/cn";
import { formatScorePair, resolveDisplayScore } from "@/lib/helpers/score";
import type { CriterionDecisionRow, ErrorCode } from "@/lib/types/domain";
import type { EvaluationWorkflowState } from "@/lib/types/enums";
import { StatusBadge } from "@/components/layout/PageHeader";

const ERROR_LABELS: Record<ErrorCode, string> = {
  CONCEPT: "Conceptual",
  FORMULA: "Formula",
  METHOD: "Method",
  CALCULATION: "Calculation",
  ALGEBRA: "Algebra",
  SIGN: "Sign",
  SUBSTITUTION: "Substitution",
  NOTATION: "Notation",
  UNIT: "Unit",
  DIAGRAM: "Diagram",
  INTERPRETATION: "Interpretation",
  INCOMPLETE: "Incomplete",
  LOGIC_REASONING: "Logic",
  PRESENTATION: "Presentation",
  FINAL_ANSWER: "Final answer",
  UNREADABLE: "Unreadable",
  OCR_TRANSCRIPTION: "OCR / transcription",
  QUESTION_MAPPING: "Question mapping",
  IDENTITY_MAPPING: "Identity mapping",
  VALID_ALTERNATIVE: "Valid alternative",
  RUBRIC_AMBIGUITY: "Rubric ambiguity",
  OTHER_REVIEW_REQUIRED: "Other review",
};

export function ErrorCategoryBadge({ code }: { code: ErrorCode }) {
  const systemish = [
    "UNREADABLE",
    "OCR_TRANSCRIPTION",
    "QUESTION_MAPPING",
    "IDENTITY_MAPPING",
    "VALID_ALTERNATIVE",
    "RUBRIC_AMBIGUITY",
    "OTHER_REVIEW_REQUIRED",
  ].includes(code);

  return (
    <span
      data-testid={`error-badge-${code}`}
      className={cn(
        "inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        systemish
          ? "bg-slate-100 text-slate-700 ring-slate-200"
          : "bg-amber-50 text-amber-900 ring-amber-200",
      )}
    >
      {ERROR_LABELS[code] ?? code}
    </span>
  );
}

export function ScoreDisplay({
  score,
  max,
  finalApproved,
  size = "md",
}: {
  score: number;
  max: number;
  finalApproved?: number | null;
  size?: "sm" | "md" | "lg";
}) {
  const display = resolveDisplayScore(score, finalApproved ?? null);
  return (
    <div
      data-testid="score-display"
      className={cn(
        "tabular-nums font-semibold text-slate-900",
        size === "sm" && "text-sm",
        size === "md" && "text-xl",
        size === "lg" && "text-3xl",
      )}
    >
      {formatScorePair(display, max)}
    </div>
  );
}

export function ScoreBreakdown({
  criteria,
}: {
  criteria: CriterionDecisionRow[];
}) {
  if (criteria.length === 0) {
    return (
      <p className="text-sm text-slate-500" data-testid="score-breakdown-empty">
        No criterion decisions recorded.
      </p>
    );
  }

  return (
    <ul data-testid="score-breakdown" className="space-y-2">
      {criteria.map((c) => (
        <RubricCriterionRow key={c.rubric_criterion_id} criterion={c} />
      ))}
    </ul>
  );
}

export function RubricCriterionRow({
  criterion,
}: {
  criterion: CriterionDecisionRow;
}) {
  return (
    <li
      data-testid={`rubric-criterion-${criterion.rubric_criterion_id}`}
      className="rounded-md border border-slate-200 bg-white px-3 py-2"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-slate-900">
            {criterion.criterion_label}
          </div>
          {criterion.deduction_reason && (
            <p className="mt-1 text-xs text-slate-600">
              {criterion.deduction_reason}
            </p>
          )}
          {criterion.error_code && (
            <div className="mt-1.5">
              <ErrorCategoryBadge code={criterion.error_code} />
            </div>
          )}
        </div>
        <div className="text-right shrink-0">
          <div className="text-sm font-semibold tabular-nums text-slate-900">
            {criterion.final_marks ?? criterion.proposed_marks}/
            {criterion.max_marks}
          </div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500">
            {criterion.decision}
          </div>
        </div>
      </div>
    </li>
  );
}

export function QuestionScore({
  code,
  score,
  max,
  state,
}: {
  code: string;
  score: number;
  max: number;
  state: EvaluationWorkflowState;
}) {
  return (
    <div
      data-testid={`question-score-${code}`}
      className="flex items-center justify-between gap-2"
    >
      <span className="text-sm font-medium text-slate-800">{code}</span>
      <div className="flex items-center gap-2">
        <span className="text-sm tabular-nums text-slate-700">
          {formatScorePair(score, max)}
        </span>
        <StatusBadge kind="evaluation" state={state} />
      </div>
    </div>
  );
}
