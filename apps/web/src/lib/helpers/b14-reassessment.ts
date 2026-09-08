import type {
  LiveImprovementAssessment,
  LiveImprovementAssessmentItem,
  ReassessmentInstantiateItem,
  ReassessmentInstantiateRequest,
  ReassessmentMasteryDelta,
} from "@/lib/types/domain";

export const B14_INSUFFICIENT_EVIDENCE_LABEL =
  "Insufficient decisive evidence";

/** True only when blueprint is APPROVED (create form gate). */
export function canCreateReassessmentFromBlueprint(
  blueprint: Pick<LiveImprovementAssessment, "status"> | null | undefined,
): boolean {
  return blueprint?.status === "APPROVED";
}

export function suggestedMarksPrefill(
  item: Pick<LiveImprovementAssessmentItem, "suggested_marks">,
): string {
  if (item.suggested_marks === null || item.suggested_marks === undefined) {
    return "1.00";
  }
  const n = Number(item.suggested_marks);
  if (!Number.isFinite(n) || n <= 0) return "1.00";
  return n.toFixed(2);
}

export function defaultPromptForItem(
  item: Pick<
    LiveImprovementAssessmentItem,
    "focus" | "item_code" | "node_title" | "node_code"
  >,
): string {
  const node = item.node_title ?? item.node_code ?? "target node";
  return `Reassessment ${item.item_code}: ${item.focus} (${node})`;
}

export function buildInstantiateRequestFromBlueprintItems(
  items: LiveImprovementAssessmentItem[],
  drafts: Record<
    string,
    { prompt_text: string; max_marks: string }
  >,
): ReassessmentInstantiateRequest {
  const payloadItems: ReassessmentInstantiateItem[] = items.map((item) => {
    const draft = drafts[item.id];
    return {
      improvement_assessment_item_id: item.id,
      prompt_text: (draft?.prompt_text ?? defaultPromptForItem(item)).trim(),
      max_marks: (draft?.max_marks ?? suggestedMarksPrefill(item)).trim(),
    };
  });
  return { items: payloadItems };
}

/** Format a mastery ratio or delta; null → insufficient evidence (never "0"). */
export function formatMasteryValue(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return B14_INSUFFICIENT_EVIDENCE_LABEL;
  }
  return value.toFixed(3);
}

export function formatSignedDelta(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return B14_INSUFFICIENT_EVIDENCE_LABEL;
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(3)}`;
}

export type B14DeltaTone = "improvement" | "regression" | "neutral" | "insufficient";

export function deltaTone(value: number | null | undefined): B14DeltaTone {
  if (value === null || value === undefined) return "insufficient";
  if (value > 0) return "improvement";
  if (value < 0) return "regression";
  return "neutral";
}

export function deltaToneClass(tone: B14DeltaTone): string {
  switch (tone) {
    case "improvement":
      return "text-teal-800";
    case "regression":
      return "text-rose-800";
    case "insufficient":
      return "text-slate-500";
    default:
      return "text-slate-700";
  }
}

export function hasMaterializedPostEvidence(
  delta: Pick<ReassessmentMasteryDelta, "materialized_at" | "post_snapshot_id">,
): boolean {
  return Boolean(delta.materialized_at || delta.post_snapshot_id);
}

export function reassessmentHasMaterializedDeltas(
  deltas: ReassessmentMasteryDelta[],
): boolean {
  return deltas.some(hasMaterializedPostEvidence);
}
