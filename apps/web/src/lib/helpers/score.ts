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

export function resolveDisplayScore(
  proposed: number,
  finalApproved: number | null,
): number {
  return finalApproved ?? proposed;
}

export function formatScore(score: number, max: number): string {
  return `${resolveDisplayScore(score, null) === score ? score : score}/${max}`;
}

export function formatScorePair(score: number, max: number): string {
  return `${score} / ${max}`;
}
