"use client";

import { cn } from "@/lib/utils/cn";
import type {
  ImprovementAssessmentBlueprint,
  LearningPathStepItem,
  LiveImprovementAssessment,
  LiveImprovementAssessmentItem,
  LiveLearningPathStep,
  LiveLearningRecommendation,
  Reassessment,
  ReassessmentMasteryDelta,
  StudentResourceAssignment,
  TopicPriority,
} from "@/lib/types/domain";
import type { ErrorCode } from "@/lib/types/domain";
import { ErrorCategoryBadge } from "@/components/evaluation/ScoreComponents";
import {
  B14_INSUFFICIENT_EVIDENCE_LABEL,
  defaultPromptForItem,
  deltaTone,
  deltaToneClass,
  formatMasteryValue,
  formatSignedDelta,
  hasMaterializedPostEvidence,
  reassessmentHasMaterializedDeltas,
  suggestedMarksPrefill,
} from "@/lib/helpers/b14-reassessment";
import Link from "next/link";
import { useState } from "react";

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
            After approval, instantiate a DRAFT reassessment assessment with
            teacher-authored prompts and marks.
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
          Blueprint approved. Instantiate a DRAFT reassessment assessment below
          when ready; answer key, rubric, READY, evaluation, and publication
          remain the existing workflow.
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

/** B13 assigned catalog resources — distinct from B9 recommendations. */
export function AssignedResourcesSection({
  assignments,
  loading,
  error,
  onRetry,
  onCancel,
  cancelPending,
}: {
  assignments: StudentResourceAssignment[];
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  onCancel?: (assignmentId: string) => void;
  cancelPending?: boolean;
}) {
  const active = assignments.filter((a) => a.status === "ASSIGNED");

  return (
    <section
      data-testid="b13-assigned-resources"
      className="mt-6 rounded-md border border-slate-200 bg-white p-4"
    >
      <h2 className="text-sm font-semibold text-slate-800">
        Assigned catalog resources (B13)
      </h2>
      <p
        data-testid="b13-recommendation-vs-assignment-note"
        className="mt-1 text-xs text-slate-600"
      >
        Assigned catalog resources (B13) are institution-approved materials.
        They are separate from B9 learning recommendations, which only prioritize
        curriculum gaps.
      </p>

      {loading && (
        <p className="mt-3 text-sm text-slate-600" data-testid="b13-assignments-loading">
          Loading assignments…
        </p>
      )}
      {error && (
        <div className="mt-3 flex items-center gap-2 text-sm text-rose-700">
          <span>Could not load assigned resources.</span>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="underline"
              data-testid="b13-assignments-retry"
            >
              Retry
            </button>
          )}
        </div>
      )}
      {!loading && !error && active.length === 0 && (
        <p
          data-testid="b13-assignments-empty"
          className="mt-3 text-sm text-slate-600"
        >
          No catalog resources assigned yet.
        </p>
      )}
      {!loading && !error && active.length > 0 && (
        <ul className="mt-3 space-y-2">
          {active.map((assignment) => (
            <li
              key={assignment.id}
              data-testid="b13-assignment-row"
              className="flex flex-wrap items-start justify-between gap-2 rounded-md border border-slate-100 bg-slate-50 px-3 py-2"
            >
              <div>
                <div className="text-sm font-medium text-slate-900">
                  {assignment.resource.title}
                </div>
                <div className="text-xs text-slate-600">
                  {assignment.resource.code} · {assignment.resource.resource_kind}{" "}
                  · {assignment.resource.content_ref}
                </div>
                {assignment.learning_recommendation_id && (
                  <div className="mt-0.5 text-xs text-slate-500">
                    Linked to recommendation {assignment.learning_recommendation_id}
                  </div>
                )}
              </div>
              {onCancel && (
                <button
                  type="button"
                  data-testid="b13-cancel-assignment"
                  disabled={cancelPending}
                  onClick={() => onCancel(assignment.id)}
                  className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                >
                  Cancel assignment
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function AssignResourcePanel({
  resources,
  recommendations,
  selectedResourceId,
  selectedRecommendationId,
  onSelectResource,
  onSelectRecommendation,
  onAssign,
  assigning,
  errorMessage,
}: {
  resources: Array<{ id: string; code: string; title: string; status: string }>;
  recommendations?: Array<{ id: string; code: string; title: string }>;
  selectedResourceId: string;
  selectedRecommendationId: string;
  onSelectResource: (id: string) => void;
  onSelectRecommendation: (id: string) => void;
  onAssign: () => void;
  assigning?: boolean;
  errorMessage?: string | null;
}) {
  return (
    <div
      data-testid="b13-assign-resource"
      className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3"
    >
      <h3 className="text-xs font-semibold uppercase tracking-wide text-teal-800">
        Assign catalog resource
      </h3>
      <p className="mt-1 text-xs text-slate-600">
        Choose an ACTIVE institution catalog resource. No open-web URLs.
      </p>
      <div className="mt-2 flex flex-wrap items-end gap-3">
        <label className="block text-xs text-slate-700">
          Resource
          <select
            data-testid="b13-assign-resource-select"
            className="mt-1 block min-w-[14rem] rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            value={selectedResourceId}
            onChange={(e) => onSelectResource(e.target.value)}
          >
            <option value="">Select resource…</option>
            {resources.map((r) => (
              <option key={r.id} value={r.id}>
                {r.code} · {r.title}
              </option>
            ))}
          </select>
        </label>
        {recommendations && recommendations.length > 0 && (
          <label className="block text-xs text-slate-700">
            Link recommendation (optional)
            <select
              data-testid="b13-assign-recommendation-select"
              className="mt-1 block min-w-[14rem] rounded-md border border-slate-300 px-2 py-1.5 text-sm"
              value={selectedRecommendationId}
              onChange={(e) => onSelectRecommendation(e.target.value)}
            >
              <option value="">None</option>
              {recommendations.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.code} · {r.title}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          type="button"
          data-testid="b13-assign-resource-submit"
          disabled={!selectedResourceId || assigning}
          onClick={onAssign}
          className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
        >
          {assigning ? "Assigning…" : "Assign resource"}
        </button>
      </div>
      {errorMessage && (
        <p className="mt-2 text-sm text-rose-700" data-testid="b13-assign-error">
          {errorMessage}
        </p>
      )}
    </div>
  );
}

function MasteryDeltaRow({
  label,
  baseline,
  post,
  delta,
}: {
  label: string;
  baseline: number | null;
  post: number | null;
  delta: number | null;
}) {
  const tone = deltaTone(delta);
  return (
    <div
      data-testid="b14-mastery-delta"
      className="rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-sm"
    >
      <div className="font-medium text-slate-800">{label}</div>
      <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
        <span>
          Baseline:{" "}
          {baseline === null ? (
            <span data-testid="b14-insufficient-evidence">
              {B14_INSUFFICIENT_EVIDENCE_LABEL}
            </span>
          ) : (
            formatMasteryValue(baseline)
          )}
        </span>
        <span>→</span>
        <span>
          Post:{" "}
          {post === null ? (
            <span data-testid="b14-insufficient-evidence">
              {B14_INSUFFICIENT_EVIDENCE_LABEL}
            </span>
          ) : (
            formatMasteryValue(post)
          )}
        </span>
        <span className={cn("font-semibold", deltaToneClass(tone))}>
          Δ{" "}
          {delta === null ? (
            <span data-testid="b14-insufficient-evidence">
              {B14_INSUFFICIENT_EVIDENCE_LABEL}
            </span>
          ) : (
            formatSignedDelta(delta)
          )}
        </span>
      </div>
    </div>
  );
}

function nodeLabelForDelta(
  delta: ReassessmentMasteryDelta,
  reassessment: Reassessment,
): string {
  const item = reassessment.items.find(
    (i) => i.curriculum_node_id === delta.curriculum_node_id,
  );
  if (item) {
    return `${item.item_code_snapshot} · ${delta.curriculum_node_id.slice(0, 8)}`;
  }
  return delta.curriculum_node_id;
}

/** B14 reassessment history — distinct from B9 recommendations and B13 resources. */
export function ReassessmentsSection({
  reassessments,
  loading,
  error,
  onRetry,
}: {
  reassessments: Reassessment[];
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
}) {
  return (
    <section
      data-testid="b14-reassessments-section"
      className="mt-6 rounded-md border border-slate-200 bg-white p-4"
    >
      <h2 className="text-sm font-semibold text-slate-800">Reassessment</h2>
      <p className="mt-1 text-xs text-slate-600">
        B14 mastery updates from published reassessments. Separate from B9
        recommendations and B13 assigned catalog resources.
      </p>

      {loading && (
        <p className="mt-3 text-sm text-slate-600">Loading reassessments…</p>
      )}
      {error && (
        <div className="mt-3 flex items-center gap-2 text-sm text-rose-700">
          <span>Could not load reassessments.</span>
          {onRetry && (
            <button type="button" onClick={onRetry} className="underline">
              Retry
            </button>
          )}
        </div>
      )}
      {!loading && !error && reassessments.length === 0 && (
        <p className="mt-3 text-sm text-slate-600">No reassessments yet.</p>
      )}
      {!loading &&
        !error &&
        reassessments.map((row) => {
          const materialized = reassessmentHasMaterializedDeltas(
            row.mastery_deltas,
          );
          return (
            <article
              key={row.id}
              data-testid="b14-reassessment-row"
              className="mt-4 rounded-md border border-slate-200 px-3 py-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="text-sm font-medium text-slate-900">
                    {row.blueprint_title}
                  </div>
                  <div className="mt-0.5 text-xs text-slate-600">
                    Status {row.status} · Assessment {row.assessment_status} ·{" "}
                    <Link
                      href={`/assessments/${row.assessment_id}`}
                      className="text-teal-800 underline"
                    >
                      {row.assessment_id}
                    </Link>
                  </div>
                </div>
                <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700 ring-1 ring-inset ring-slate-200">
                  {row.status}
                </span>
              </div>

              {!materialized && (
                <p
                  data-testid="b14-pre-publication-message"
                  className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900"
                >
                  Post-reassessment mastery evidence is not available until the
                  linked assessment is published and analytics materialization
                  completes.
                </p>
              )}

              {materialized && (
                <div className="mt-3 space-y-3">
                  {row.mastery_deltas.map((delta) => (
                    <div
                      key={delta.curriculum_node_id}
                      className="space-y-2"
                      data-testid={`b14-node-${delta.curriculum_node_id}`}
                    >
                      <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                        Node {nodeLabelForDelta(delta, row)}
                        {!hasMaterializedPostEvidence(delta) ? (
                          <span className="ml-2 font-normal normal-case text-slate-500">
                            (awaiting post evidence)
                          </span>
                        ) : null}
                      </div>
                      <MasteryDeltaRow
                        label="Concept"
                        baseline={delta.baseline_concept_mastery}
                        post={delta.post_concept_mastery}
                        delta={delta.concept_delta}
                      />
                      <MasteryDeltaRow
                        label="Execution"
                        baseline={delta.baseline_execution_accuracy}
                        post={delta.post_execution_accuracy}
                        delta={delta.execution_delta}
                      />
                    </div>
                  ))}
                </div>
              )}
            </article>
          );
        })}
    </section>
  );
}

/** B14 create form — only render when blueprint status is APPROVED. */
export function CreateReassessmentForm({
  blueprintId,
  items,
  onSubmit,
  submitting,
  errorMessage,
  created,
}: {
  blueprintId: string;
  items: LiveImprovementAssessmentItem[];
  onSubmit: (
    drafts: Record<string, { prompt_text: string; max_marks: string }>,
  ) => void;
  submitting?: boolean;
  errorMessage?: string | null;
  created?: Reassessment | null;
}) {
  const [drafts, setDrafts] = useState<
    Record<string, { prompt_text: string; max_marks: string }>
  >(() => {
    const initial: Record<string, { prompt_text: string; max_marks: string }> =
      {};
    for (const item of items) {
      initial[item.id] = {
        prompt_text: defaultPromptForItem(item),
        max_marks: suggestedMarksPrefill(item),
      };
    }
    return initial;
  });

  return (
    <section
      data-testid="b14-create-reassessment"
      className="mt-6 rounded-md border border-slate-200 bg-white p-4"
    >
      <h2 className="text-sm font-semibold text-slate-800">
        Create reassessment (B14)
      </h2>
      <p className="mt-1 text-xs text-slate-600">
        Teacher-authored prompts and marks instantiate a DRAFT Assessment linked
        to this APPROVED blueprint ({blueprintId}).
      </p>

      <div className="mt-4 space-y-4">
        {items.map((item) => {
          const draft = drafts[item.id] ?? {
            prompt_text: defaultPromptForItem(item),
            max_marks: suggestedMarksPrefill(item),
          };
          return (
            <div
              key={item.id}
              data-testid={`b14-create-item-${item.item_code}`}
              className="rounded-md border border-slate-100 bg-slate-50 p-3"
            >
              <div className="text-sm font-medium text-slate-900">
                {item.item_code} · {item.node_code ?? item.curriculum_node_id}
                {item.node_title ? ` · ${item.node_title}` : ""}
              </div>
              <div className="mt-1 text-xs text-slate-600">
                {item.template_kind} · {item.focus} · {item.difficulty} ·
                suggested marks {item.suggested_marks ?? "—"}
              </div>
              <label className="mt-3 block text-xs text-slate-700">
                Prompt
                <textarea
                  data-testid={`b14-prompt-${item.item_code}`}
                  rows={2}
                  className="mt-1 w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  value={draft.prompt_text}
                  onChange={(e) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [item.id]: { ...draft, prompt_text: e.target.value },
                    }))
                  }
                />
              </label>
              <label className="mt-2 block text-xs text-slate-700">
                Max marks
                <input
                  data-testid={`b14-marks-${item.item_code}`}
                  type="text"
                  className="mt-1 w-32 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  value={draft.max_marks}
                  onChange={(e) =>
                    setDrafts((prev) => ({
                      ...prev,
                      [item.id]: { ...draft, max_marks: e.target.value },
                    }))
                  }
                />
              </label>
            </div>
          );
        })}
      </div>

      <button
        type="button"
        data-testid="b14-instantiate-submit"
        disabled={submitting || items.length === 0}
        onClick={() => onSubmit(drafts)}
        className="mt-4 rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900 disabled:opacity-50"
      >
        {submitting ? "Creating…" : "Instantiate reassessment"}
      </button>

      {errorMessage && (
        <p className="mt-2 text-sm text-rose-700" data-testid="b14-create-error">
          {errorMessage}
        </p>
      )}

      {created && (
        <div
          data-testid="b14-create-success"
          className="mt-4 rounded-md border border-teal-200 bg-teal-50 px-3 py-3 text-sm text-teal-900"
        >
          <p>
            Reassessment <span className="font-medium">{created.id}</span>{" "}
            created. Assessment{" "}
            <Link
              href={`/assessments/${created.assessment_id}`}
              className="font-medium underline"
              data-testid="b14-created-assessment-link"
            >
              {created.assessment_id}
            </Link>{" "}
            status {created.assessment_status || "DRAFT"}.
          </p>
          <p className="mt-2 text-xs text-teal-800">
            Answer key, rubric, READY/ACTIVE, evaluation, and publication remain
            the existing assessment workflow.
          </p>
        </div>
      )}
    </section>
  );
}
