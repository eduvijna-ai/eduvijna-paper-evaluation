import { cn } from "@/lib/utils/cn";
import type { Student, StudentMatchCandidate as Candidate } from "@/lib/types/domain";
import type { IdentityMatchState } from "@/lib/types/enums";
import { StatusBadge } from "@/components/layout/PageHeader";
import { ConfidenceIndicator } from "@/components/ui/FeedbackStates";
import { isUnresolvedConfidence } from "@/lib/helpers/confidence";

export function StudentIdentityCard({
  rollDetected,
  nameDetected,
  matchState,
  confidence,
  matchedStudent,
}: {
  rollDetected: string | null;
  nameDetected: string | null;
  matchState: IdentityMatchState;
  confidence: number;
  matchedStudent?: Student | null;
}) {
  const unresolved =
    isUnresolvedConfidence(confidence) ||
    matchState === "UNMATCHED" ||
    matchState === "REVIEW_REQUIRED";

  return (
    <div
      data-testid="student-identity-card"
      className={cn(
        "rounded-md border bg-white p-4",
        unresolved ? "border-amber-300" : "border-slate-200",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-900">
            Detected identity
          </h3>
          <dl className="mt-3 space-y-1.5 text-sm">
            <div className="flex gap-2">
              <dt className="w-16 text-slate-500">Roll</dt>
              <dd className="font-medium text-slate-900">
                {rollDetected ?? "—"}
              </dd>
            </div>
            <div className="flex gap-2">
              <dt className="w-16 text-slate-500">Name</dt>
              <dd className="font-medium text-slate-900">
                {nameDetected ?? "—"}
              </dd>
            </div>
            {matchedStudent && (
              <div className="flex gap-2">
                <dt className="w-16 text-slate-500">Matched</dt>
                <dd className="font-medium text-slate-900">
                  {matchedStudent.display_name} ({matchedStudent.external_ref})
                </dd>
              </div>
            )}
          </dl>
        </div>
        <StatusBadge kind="identity" state={matchState} />
      </div>
      <div className="mt-4">
        <ConfidenceIndicator value={confidence} label="Identity confidence" />
      </div>
      {unresolved && (
        <p
          data-testid="identity-unresolved-banner"
          className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs text-amber-950 ring-1 ring-amber-200"
        >
          Low confidence — treat as unresolved until a roster match is confirmed.
        </p>
      )}
    </div>
  );
}

export function StudentMatchCandidate({
  candidate,
  selected,
  onSelect,
  showSourceType,
}: {
  candidate: Candidate;
  selected?: boolean;
  onSelect?: () => void;
  /** When true, distinguish AI-assisted suggestions from manual roster rows */
  showSourceType?: boolean;
}) {
  const isAiSuggestion = candidate.source_type === "AI";
  return (
    <button
      type="button"
      data-testid={`match-candidate-${candidate.student_id}`}
      onClick={onSelect}
      className={cn(
        "w-full rounded-md border bg-white p-3 text-left transition-colors",
        selected
          ? "border-teal-600 ring-1 ring-teal-600"
          : "border-slate-200 hover:border-slate-300",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-slate-900">
            {candidate.display_name}
          </div>
          <div className="text-xs text-slate-500">
            Roll {candidate.external_ref} · Grade {candidate.grade}
            {candidate.section}
          </div>
          {showSourceType && (
            <span
              data-testid={`candidate-source-${candidate.student_id}`}
              className={cn(
                "mt-1 inline-flex rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
                isAiSuggestion
                  ? "bg-violet-50 text-violet-800 ring-violet-200"
                  : "bg-slate-50 text-slate-700 ring-slate-200",
              )}
            >
              {isAiSuggestion ? "AI-assisted suggestion" : "Manual roster selection"}
            </span>
          )}
        </div>
      </div>
      <div className="mt-2">
        <ConfidenceIndicator value={candidate.confidence} />
      </div>
      <ul className="mt-2 list-disc space-y-0.5 pl-4 text-xs text-slate-600">
        {candidate.match_reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </button>
  );
}
