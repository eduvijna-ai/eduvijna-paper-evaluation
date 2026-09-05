import type { Confidence } from "@/lib/types/domain";

export type ConfidenceLevel = "high" | "medium" | "low" | "critical";

export const CONFIDENCE_THRESHOLDS = {
  high: 0.85,
  medium: 0.65,
  low: 0.4,
} as const;

export function getConfidenceLevel(value: Confidence): ConfidenceLevel {
  if (value >= CONFIDENCE_THRESHOLDS.high) return "high";
  if (value >= CONFIDENCE_THRESHOLDS.medium) return "medium";
  if (value >= CONFIDENCE_THRESHOLDS.low) return "low";
  return "critical";
}

export function isUnresolvedConfidence(value: Confidence): boolean {
  return value < CONFIDENCE_THRESHOLDS.medium;
}

export function formatConfidence(value: Confidence): string {
  return `${Math.round(value * 100)}%`;
}
