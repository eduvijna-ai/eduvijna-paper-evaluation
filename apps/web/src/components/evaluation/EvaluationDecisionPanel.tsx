"use client";

import { useState } from "react";
import type { EvaluationLedger } from "@/lib/types/domain";
import type { TeacherReviewAction } from "@/lib/types/enums";
import { ConfidenceIndicator } from "@/components/ui/FeedbackStates";
import {
  ErrorCategoryBadge,
  ScoreBreakdown,
  ScoreDisplay,
} from "@/components/evaluation/ScoreComponents";
import { StatusBadge } from "@/components/layout/PageHeader";
import { ConfirmDialog } from "@/components/ui/DataTable";
import { cn } from "@/lib/utils/cn";
import {
  canAcceptProposedScore,
  isLiveDisabledTeacherAction,
  validateEscalateReason,
  validateOverrideReason,
} from "@/lib/helpers/teacher-actions";
import { getApiCapabilities } from "@/lib/api/capabilities";

const ACTIONS: Array<{
  action: TeacherReviewAction;
  label: string;
  tone?: "default" | "danger";
}> = [
  { action: "ACCEPT", label: "Accept" },
  { action: "CHANGE_SCORE", label: "Change score / override" },
  { action: "EDIT_FEEDBACK", label: "Edit feedback" },
  { action: "VALID_ALTERNATIVE", label: "Valid alternative" },
  { action: "OCR_TRANSCRIPTION_ERROR", label: "OCR / transcription error" },
  { action: "MAPPING_ERROR", label: "Mapping error" },
  { action: "ESCALATE", label: "Escalate", tone: "danger" },
];

function needsReason(action: TeacherReviewAction): boolean {
  return (
    action === "CHANGE_SCORE" ||
    action === "EDIT_FEEDBACK" ||
    action === "ESCALATE" ||
    action === "VALID_ALTERNATIVE"
  );
}

export function TeacherReviewActions({
  onAction,
  disabled,
  acceptDisabled,
  liveMode,
}: {
  onAction: (
    action: TeacherReviewAction,
    payload?: { newScore?: number; feedback?: string },
  ) => void;
  disabled?: boolean;
  acceptDisabled?: boolean;
  liveMode?: boolean;
}) {
  const [pending, setPending] = useState<TeacherReviewAction | null>(null);
  const [score, setScore] = useState("");
  const [feedback, setFeedback] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const visibleActions = ACTIONS.filter((item) => {
    if (!liveMode) return true;
    // Hide non-live correction workflows in live mode (also shown disabled below if kept)
    return !isLiveDisabledTeacherAction(item.action);
  });

  const disabledLiveActions = liveMode
    ? ACTIONS.filter((item) => isLiveDisabledTeacherAction(item.action))
    : [];

  return (
    <div data-testid="teacher-review-actions" className="space-y-3">
      <div className="grid grid-cols-1 gap-2">
        {visibleActions.map((item) => {
          const isAccept = item.action === "ACCEPT";
          const buttonDisabled =
            disabled || (isAccept && Boolean(acceptDisabled));
          return (
            <button
              key={item.action}
              type="button"
              disabled={buttonDisabled}
              data-testid={`teacher-action-${item.action}`}
              title={
                isAccept && acceptDisabled
                  ? "No automatic score proposed. Human review required."
                  : undefined
              }
              onClick={() => {
                setFormError(null);
                setPending(item.action);
              }}
              className={cn(
                "rounded-md border px-3 py-2 text-left text-sm font-medium transition-colors disabled:opacity-50",
                item.tone === "danger"
                  ? "border-rose-200 text-rose-800 hover:bg-rose-50"
                  : "border-slate-200 text-slate-800 hover:bg-slate-50",
              )}
            >
              {item.label}
            </button>
          );
        })}
        {disabledLiveActions.map((item) => (
          <button
            key={item.action}
            type="button"
            disabled
            data-testid={`teacher-action-${item.action}`}
            title="Correction workflow not live yet"
            className="rounded-md border border-slate-200 px-3 py-2 text-left text-sm font-medium text-slate-400 opacity-60"
          >
            {item.label}
            <span className="mt-0.5 block text-xs font-normal text-slate-500">
              Correction workflow not live yet
            </span>
          </button>
        ))}
      </div>

      {pending && needsReason(pending) && (
        <div className="space-y-2 rounded-md border border-slate-200 bg-slate-50 p-3">
          {pending === "CHANGE_SCORE" && (
            <label className="block text-xs font-medium text-slate-600">
              New score
              <input
                data-testid="teacher-new-score"
                type="number"
                value={score}
                onChange={(e) => setScore(e.target.value)}
                className="mt-1 w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm"
              />
            </label>
          )}
          <label className="block text-xs font-medium text-slate-600">
            {pending === "CHANGE_SCORE" || pending === "ESCALATE"
              ? "Reason (required)"
              : "Feedback"}
            <textarea
              data-testid="teacher-feedback"
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-slate-200 px-2 py-1.5 text-sm"
            />
          </label>
          {formError && (
            <p data-testid="teacher-action-form-error" className="text-xs text-rose-700">
              {formError}
            </p>
          )}
        </div>
      )}

      <ConfirmDialog
        open={pending !== null}
        title={pending ? `Confirm: ${pending.replaceAll("_", " ")}` : ""}
        description="This updates the evaluation ledger workflow for the selected question."
        confirmLabel="Apply"
        onCancel={() => {
          setPending(null);
          setFormError(null);
        }}
        onConfirm={() => {
          if (!pending) return;
          if (pending === "CHANGE_SCORE") {
            const err = validateOverrideReason(feedback);
            if (err) {
              setFormError(err);
              return;
            }
            if (score === "" || Number.isNaN(Number(score))) {
              setFormError("Override requires a new score.");
              return;
            }
          }
          if (pending === "ESCALATE") {
            const err = validateEscalateReason(feedback);
            if (err) {
              setFormError(err);
              return;
            }
          }
          onAction(pending, {
            newScore: score !== "" ? Number(score) : undefined,
            feedback: feedback || undefined,
          });
          setPending(null);
          setScore("");
          setFeedback("");
          setFormError(null);
        }}
      />
    </div>
  );
}

export function EvaluationDecisionPanel({
  ledger,
  onAction,
  liveMode,
  disabled,
}: {
  ledger: EvaluationLedger;
  onAction: (
    action: TeacherReviewAction,
    payload?: { newScore?: number; feedback?: string },
  ) => void;
  liveMode?: boolean;
  disabled?: boolean;
}) {
  const live = liveMode ?? getApiCapabilities().evaluation === "live";
  const acceptDisabled = !canAcceptProposedScore(ledger.proposed_ai_score);
  const sources = ledger.score_sources;

  return (
    <section
      data-testid="evaluation-decision-panel"
      className="flex h-full flex-col gap-4 overflow-y-auto"
    >
      <div>
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Evaluation decision
          </h2>
          <StatusBadge kind="evaluation" state={ledger.workflow_state} />
        </div>
        <div className="mt-3">
          <ScoreDisplay
            score={ledger.proposed_ai_score}
            max={ledger.max_mark}
            finalApproved={ledger.final_human_approved_score}
            size="lg"
          />
          <p className="mt-1 text-xs text-slate-500">
            {ledger.proposed_ai_score === null
              ? "AI proposal unavailable"
              : "Proposed AI score"}
            {ledger.final_human_approved_score !== null &&
              ` · Human final: ${ledger.final_human_approved_score}`}
          </p>
        </div>
      </div>

      <div
        data-testid="score-source-legend"
        className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700"
      >
        <p className="font-medium text-slate-800">Score sources</p>
        <ul className="mt-1 space-y-0.5">
          <li data-testid="source-ai-proposal">
            AI proposal: {sources?.ai_proposal ? "present" : "none"}
          </li>
          <li data-testid="source-deterministic">
            Deterministic verification:{" "}
            {sources?.deterministic_verification ? "present" : "not run"}
          </li>
          <li data-testid="source-human-final">
            Human final: {sources?.human_final ? "set" : "pending"}
          </li>
        </ul>
      </div>

      <div className="space-y-2" data-testid="confidence-dimensions">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
          Confidence dimensions
        </h3>
        <ConfidenceIndicator
          value={ledger.identity_confidence}
          label="Identity"
        />
        <ConfidenceIndicator
          value={ledger.mapping_confidence}
          label="Mapping"
        />
        <ConfidenceIndicator
          value={ledger.transcription_confidence}
          label="Transcription"
        />
        <ConfidenceIndicator
          value={ledger.evaluation_confidence}
          label="Evaluation"
        />
        <ConfidenceIndicator
          value={ledger.math_verification_confidence}
          label="Math verification"
        />
      </div>

      {ledger.math_verification_summary && (
        <div data-testid="math-verification-summary">
          <h3 className="mb-1 text-sm font-semibold text-slate-800">
            Math verification
          </h3>
          <p className="text-sm text-slate-700">{ledger.math_verification_summary}</p>
        </div>
      )}

      {ledger.error_codes.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-800">Errors</h3>
          <div className="flex flex-wrap gap-1.5">
            {ledger.error_codes.map((code) => (
              <ErrorCategoryBadge key={code} code={code} />
            ))}
          </div>
        </div>
      )}

      <div>
        <h3 className="mb-1 text-sm font-semibold text-slate-800">
          First divergence
        </h3>
        <p className="text-sm text-slate-700">
          {ledger.criterion_decisions.find(
            (c) => c.decision === "PARTIAL" || c.decision === "DEDUCTED",
          )?.deduction_reason ??
            (ledger.error_codes[0]
              ? `First flagged: ${ledger.error_codes[0]}`
              : "No divergence recorded.")}
        </p>
      </div>

      <div>
        <h3 className="mb-1 text-sm font-semibold text-slate-800">
          Alternative approach
        </h3>
        <p className="text-sm text-slate-700 whitespace-pre-wrap">
          {ledger.alternative_method_label ||
            (ledger.error_codes.includes("VALID_ALTERNATIVE")
              ? "Student used a valid alternative method."
              : ledger.corrected_approach) ||
            "—"}
        </p>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-slate-800">
          Criterion decisions / deductions
        </h3>
        <ScoreBreakdown criteria={ledger.criterion_decisions} />
      </div>

      <div>
        <h3 className="mb-1 text-sm font-semibold text-slate-800">
          Feedback draft
        </h3>
        <p className="text-sm text-slate-700 whitespace-pre-wrap">
          {ledger.feedback_draft || "—"}
        </p>
      </div>

      <div>
        <h3 className="mb-1 text-sm font-semibold text-slate-800">
          Corrected approach
        </h3>
        <p className="text-sm text-slate-700 whitespace-pre-wrap">
          {ledger.corrected_approach || "—"}
        </p>
      </div>

      {ledger.ecf_applied && (
        <p
          data-testid="ecf-applied"
          className="rounded-md bg-sky-50 px-3 py-2 text-xs text-sky-900 ring-1 ring-sky-200"
        >
          Error carried forward (ECF) applied on this question.
        </p>
      )}

      <div className="border-t border-slate-200 pt-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-800">
          Teacher actions
        </h3>
        <TeacherReviewActions
          onAction={onAction}
          acceptDisabled={acceptDisabled}
          liveMode={live}
          disabled={disabled}
        />
      </div>
    </section>
  );
}
