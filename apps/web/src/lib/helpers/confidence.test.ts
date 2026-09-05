import { describe, expect, it } from "vitest";
import {
  formatConfidence,
  getConfidenceLevel,
  isUnresolvedConfidence,
} from "./confidence";

describe("confidence thresholds", () => {
  it("classifies levels", () => {
    expect(getConfidenceLevel(0.9)).toBe("high");
    expect(getConfidenceLevel(0.7)).toBe("medium");
    expect(getConfidenceLevel(0.5)).toBe("low");
    expect(getConfidenceLevel(0.2)).toBe("critical");
  });

  it("flags unresolved below medium threshold", () => {
    expect(isUnresolvedConfidence(0.64)).toBe(true);
    expect(isUnresolvedConfidence(0.65)).toBe(false);
  });

  it("formats percent", () => {
    expect(formatConfidence(0.48)).toBe("48%");
  });
});
