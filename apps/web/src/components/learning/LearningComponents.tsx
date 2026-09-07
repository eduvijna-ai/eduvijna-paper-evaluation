"use client";

import { cn } from "@/lib/utils/cn";
import type {
  ImprovementAssessmentBlueprint,
  LearningPathStepItem,
  LiveImprovementAssessment,
  LiveLearningPathStep,
  LiveLearningRecommendation,
  TopicPriority,
} from "@/lib/types/domain";
import type { ErrorCode } from "@/lib/types/domain";
import { ErrorCategoryBadge } from "@/components/evaluation/ScoreComponents";

export function ConceptMasteryBar({
  concept,
  mastery,
}: {
  concept: string;
  mastery: number;
}) {
  return (
    <div data-testid={`concept-mastery-${concept}`} className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-slate-700">{concept}</span>
        <span className="tabular-nums text-slate-500">
          {Math.round(mastery * 100)}%
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-teal-700"
          style={{ width: `${Math.round(mastery * 100)}%` }}
        />
      </div>
    </div>
  );
}

export function TopicPriorityCard({ topic }: { topic: TopicPriority }) {
  return (
    <div
      data-testid={`topic-priority-${topic.priority}`}
      className="rounded-md border border-slate-200 bg-white p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-teal-800">
            Priority {topic.priority}
          </div>
          <h3 className="mt-1 text-sm font-semibold text-slate-900">
            {topic.topic}
          </h3>
        </div>
        <span className="text-xs tabular-nums text-slate-500">
          {Math.round(topic.mastery * 100)}% mastery
        </span>
      </div>
      <p className="mt-2 text-sm text-slate-600">{topic.reason}</p>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {topic.error_codes.map((code) => (
          <ErrorCategoryBadge key={code} code={code} />
        ))}
      </div>
    </div>
  );
}

const KIND_LABELS: Record<string, string> = {
  PREREQUISITE_REPAIR: "Prerequisite repair",
  TARGET_CONCEPT: "Concept gap",
  PROCEDURE_PRACTICE: "Procedure practice",
  EXECUTION_PRACTICE: "Execution practice",
};

export function LiveRecommendationCard({
  recommendation,
}: {
  recommendation: LiveLearningRecommendation;
}) {
  return (
    <div
      data-testid={`live-recommendation-${recommendation.priority}`}
      data-node-code={recommendation.code}
      className="rounded-md border border-slate-200 bg-white p-4"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-teal-800">
            Priority {recommendation.priority}
          </div>
          <h3 className="mt-1 text-sm font-semibold text-slate-900">
            {recommendation.code}
            {recommendation.title ? ` · ${recommendation.title}` : ""}
          </h3>
          <div className="mt-1 text-xs font-medium text-slate-600">
            {KIND_LABELS[recommendation.recommendation_kind] ??
              recommendation.recommendation_kind}
          </div>
        </div>
        <span className="text-xs tabular-nums text-slate-500">
          {recommendation.evidence_count} evidence
          {recommendation.mean_evidence_score_ratio != null
            ? ` · mean ${Math.round(recommendation.mean_evidence_score_ratio * 100)}%`
            : ""}
        </span>
      </div>
      <p
        data-testid="recommendation-rationale"
        className="mt-2 text-sm text-slate-600"
      >
        {recommendation.rationale}
      </p>
      <dl className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-3">
        <div>
          <dt className="font-semibold text-slate-700">Concept</dt>
          <dd data-testid="signal-concept">{recommendation.concept_signal}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-700">Execution</dt>
          <dd data-testid="signal-execution">
            {recommendation.execution_signal}
          </dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-700">Procedure</dt>
          <dd data-testid="signal-procedure">
            {recommendation.procedure_signal}
          </dd>
        </div>
      </dl>
    </div>
  );
}

export function ErrorDistribution({
  items,
}: {
  items: Array<{ code: ErrorCode; count: number }>;
}) {
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div data-testid="error-distribution" className="space-y-2">
      {items.map((item) => (
        <div
          key={item.code}
          className="grid grid-cols-[140px_1fr_32px] items-center gap-2"
        >
          <ErrorCategoryBadge code={item.code} />
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-slate-600"
              style={{ width: `${(item.count / max) * 100}%` }}
            />
          </div>
          <span className="text-xs tabular-nums text-slate-600">
            {item.count}
          </span>
        </div>
      ))}
    </div>
  );
}

const STEP_LABELS: Record<string, string> = {
  PREREQUISITE: "Prerequisite",
  LEARN: "Learn",
  WORKED_EXAMPLE: "Worked example",
  GUIDED: "Guided",
  INDEPENDENT: "Independent",
  EXAM_STYLE: "Exam-style",
  MASTERY_CHECK: "Mastery check",
};

function pathStepBadge(step: LiveLearningPathStep): string | null {
  if (step.kind === "MASTERY_CHECK") return "Needs check";
  if (step.relationship_type === "REQUIRED") return "Required prerequisite";
  if (step.relationship_type === "RECOMMENDED") {
    return "Recommended prerequisite";
  }
  if (step.kind === "PREREQUISITE") return "Required prerequisite";
  if (step.evidence_basis === "PROCEDURE" || /procedure/i.test(step.title)) {
    return "Procedure practice";
  }
  if (step.evidence_basis === "EXECUTION" || /execution/i.test(step.title)) {
    return "Execution practice";
  }
  if (step.evidence_basis === "CONCEPT" || /concept/i.test(step.title)) {
    return "Concept gap";
  }
  return null;
}

export function LearningPathStep({
  step,
  index,
}: {
  step: LearningPathStepItem;
  index: number;
}) {
  return (
    <li
      data-testid={`learning-path-step-${step.kind}`}
      className={cn(
        "relative rounded-md border px-3 py-3",
        step.completed
          ? "border-teal-200 bg-teal-50/50"
          : "border-slate-200 bg-white",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            {index + 1}. {STEP_LABELS[step.kind] ?? step.kind}
          </div>
          <div className="mt-0.5 text-sm font-medium text-slate-900">
            {step.title}
          </div>
          <p className="mt-1 text-xs text-slate-600">{step.description}</p>
        </div>
        <div className="text-right shrink-0">
          {step.estimated_minutes != null && (
            <div className="text-xs text-slate-500">
              {step.estimated_minutes} min
            </div>
          )}
          <div
            className={cn(
              "mt-1 text-[11px] font-medium",
              step.completed ? "text-teal-700" : "text-slate-400",
            )}
          >
            {step.completed ? "Done" : "Pending"}
          </div>
        </div>
      </div>
    </li>
  );
}

export function LiveLearningPathStepRow({
  step,
  index,
}: {
  step: LiveLearningPathStep;
  index: number;
}) {
  const badge = pathStepBadge(step);
  return (
    <li
      data-testid={`live-learning-path-step-${index}`}
      data-step-kind={step.kind}
      data-node-code={step.node_code ?? undefined}
      className="relative rounded-md border border-slate-200 bg-white px-3 py-3"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            {index + 1}. {STEP_LABELS[step.kind] ?? step.kind}
          </div>
          <div className="mt-0.5 text-sm font-medium text-slate-900">
            {step.title}
          </div>
          {step.description ? (
            <p className="mt-1 text-xs text-slate-600">{step.description}</p>
          ) : null}
          {badge ? (
            <span
              data-testid="path-step-badge"
              className="mt-2 inline-flex rounded-md bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700"
            >
              {badge}
            </span>
          ) : null}
        </div>
        {step.estimated_minutes != null ? (
          <div className="text-xs text-slate-500 shrink-0">
            {step.estimated_minutes} min
          </div>
        ) : null}
      </div>
    </li>
  );
}

export function ImprovementAssessmentBlueprint({
  blueprint,
  onApprove,
}: {
  blueprint: ImprovementAssessmentBlueprint;
  onApprove?: () => void;
}) {
  return (
    <div
      data-testid="improvement-assessment-blueprint"
      className="rounded-md border border-slate-200 bg-white p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900">
            {blueprint.title}
          </h3>
          <p className="mt-1 text-sm text-slate-600">
            Teacher approval required before student release.
          </p>
        </div>
        <span
          data-testid="blueprint-state"
          className={cn(
            "inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
            blueprint.workflow_state === "APPROVED"
              ? "bg-teal-50 text-teal-800 ring-teal-200"
              : blueprint.workflow_state === "PENDING_APPROVAL"
                ? "bg-amber-50 text-amber-900 ring-amber-200"
                : "bg-slate-100 text-slate-700 ring-slate-200",
          )}
        >
          {blueprint.workflow_state.replaceAll("_", " ")}
        </span>
      </div>

      <div className="mt-4">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Target topics
        </h4>
        <ul className="mt-1 flex flex-wrap gap-2">
          {blueprint.target_topics.map((t) => (
            <li
              key={t}
              className="rounded-md bg-slate-100 px-2 py-0.5 text-xs text-slate-700"
            >
              {t}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="py-1.5 pr-3">Code</th>
              <th className="py-1.5 pr-3">Focus</th>
              <th className="py-1.5 pr-3">Marks</th>
              <th className="py-1.5">Difficulty</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {blueprint.question_outline.map((q) => (
              <tr key={q.code}>
                <td className="py-2 pr-3 font-medium">{q.code}</td>
                <td className="py-2 pr-3 text-slate-700">{q.focus}</td>
                <td className="py-2 pr-3 tabular-nums">{q.max_mark}</td>
                <td className="py-2 text-slate-600">{q.difficulty}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {blueprint.teacher_notes && (
        <p className="mt-3 text-sm text-slate-600">{blueprint.teacher_notes}</p>
      )}

      {onApprove && blueprint.workflow_state === "PENDING_APPROVAL" && (
        <button
          type="button"
          data-testid="approve-blueprint"
          onClick={onApprove}
          className="mt-4 rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
        >
          Approve blueprint
        </button>
      )}
    </div>
  );
}

export function LiveImprovementBlueprintPanel({
  blueprint,
  onApprove,
  onReject,
  rejectReason,
  onRejectReasonChange,
}: {
  blueprint: LiveImprovementAssessment;
  onApprove?: () => void;
  onReject?: () => void;
  rejectReason?: string;
  onRejectReasonChange?: (value: string) => void;
}) {
  return (
    <div
      data-testid="live-improvement-blueprint"
      className="rounded-md border border-slate-200 bg-white p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-slate-900">
            {blueprint.title}
          </h3>
          <p
            data-testid="blueprint-live-copy"
            className="mt-1 text-sm text-slate-600"
          >
            Teacher approval freezes this improvement-assessment blueprint.
            Creating or releasing a follow-up reassessment is not live in this
            CVB phase.
          </p>
        </div>
        <span
          data-testid="blueprint-state"
          className={cn(
            "inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
            blueprint.status === "APPROVED"
              ? "bg-teal-50 text-teal-800 ring-teal-200"
              : blueprint.status === "PENDING_APPROVAL"
                ? "bg-amber-50 text-amber-900 ring-amber-200"
                : blueprint.status === "FAILED" ||
                    blueprint.status === "REJECTED"
                  ? "bg-rose-50 text-rose-800 ring-rose-200"
                  : "bg-slate-100 text-slate-700 ring-slate-200",
          )}
        >
          {String(blueprint.status).replaceAll("_", " ")}
        </span>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="py-1.5 pr-3">Code</th>
              <th className="py-1.5 pr-3">Node</th>
              <th className="py-1.5 pr-3">Template</th>
              <th className="py-1.5 pr-3">Focus</th>
              <th className="py-1.5 pr-3">Marks</th>
              <th className="py-1.5">Difficulty</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {blueprint.items.map((item) => (
              <tr
                key={item.id}
                data-testid={`blueprint-item-${item.item_code}`}
              >
                <td className="py-2 pr-3 font-medium">{item.item_code}</td>
                <td className="py-2 pr-3 text-slate-700">
                  {item.node_code ?? item.curriculum_node_id.slice(0, 8)}
                  {item.node_title ? ` · ${item.node_title}` : ""}
                </td>
                <td className="py-2 pr-3 text-slate-700">
                  {item.template_kind}
                  <div className="text-[11px] text-slate-500">
                    {item.question_template_ref}
                  </div>
                </td>
                <td className="py-2 pr-3 text-slate-700">{item.focus}</td>
                <td className="py-2 pr-3 tabular-nums">
                  {item.suggested_marks ?? "—"}
                </td>
                <td className="py-2 text-slate-600">{item.difficulty}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {blueprint.status === "APPROVED" && (
        <p
          data-testid="blueprint-approved-notice"
          className="mt-4 rounded-md border border-teal-200 bg-teal-50 px-3 py-2 text-sm text-teal-900"
        >
          Blueprint approved. Follow-up assessment creation is a later phase.
        </p>
      )}

      {blueprint.status === "PENDING_APPROVAL" && (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap gap-2">
            {onApprove && (
              <button
                type="button"
                data-testid="approve-blueprint"
                onClick={onApprove}
                className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
              >
                Approve blueprint
              </button>
            )}
          </div>
          {onReject && (
            <div className="space-y-2">
              <label className="block text-xs font-medium text-slate-600">
                Rejection reason
                <textarea
                  data-testid="reject-blueprint-reason"
                  value={rejectReason ?? ""}
                  onChange={(e) => onRejectReasonChange?.(e.target.value)}
                  rows={2}
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                />
              </label>
              <button
                type="button"
                data-testid="reject-blueprint"
                onClick={onReject}
                disabled={!rejectReason?.trim()}
                className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
              >
                Reject blueprint
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
