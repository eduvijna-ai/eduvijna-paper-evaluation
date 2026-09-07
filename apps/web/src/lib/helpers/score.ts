export function clampScore(score: number, max: number): number {
  if (Number.isNaN(score) || score < 0) return 0;
  if (score > max) return max;
  return Math.round(score * 100) / 100;
}

export function computePercentage(score: number, max: number): number {
  if (max <= 0) return 0;
  return Math.round((score / max) * 1000) / 10;
}

export function sumScores(scores: number[]): number {
  return scores.reduce((acc, value) => acc + value, 0);
}

/**
 * Prefer human-approved score when present. Null proposed must stay null
 * (never coerce unreadable / missing proposals to 0).
 */
export function resolveDisplayScore(
  proposed: number | null,
  finalApproved: number | null,
): number | null {
  if (finalApproved !== null && finalApproved !== undefined) return finalApproved;
  return proposed;
}

export function formatScore(score: number, max: number): string {
  return `${score}/${max}`;
}

export function formatScorePair(score: number | null, max: number): string {
  if (score === null || score === undefined) return `— / ${max}`;
  return `${score} / ${max}`;
}

/** UI copy when AI did not propose a numeric score. */
export const NO_PROPOSAL_SCORE_MESSAGE =
  "No automatic score proposed. Human review required.";

export function formatProposedScoreLabel(
  proposed: number | null,
  max: number,
): string {
  if (proposed === null || proposed === undefined) {
    return NO_PROPOSAL_SCORE_MESSAGE;
  }
  return formatScorePair(proposed, max);
}

export function formatCriterionMarks(marks: number | null | undefined): string {
  if (marks === null || marks === undefined) return "—";
  return String(marks);
}
