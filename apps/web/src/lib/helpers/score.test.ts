import { describe, expect, it } from "vitest";
import {
  clampScore,
  computePercentage,
  resolveDisplayScore,
  sumScores,
} from "./score";

describe("score helpers", () => {
  it("clamps below zero and above max", () => {
    expect(clampScore(-1, 10)).toBe(0);
    expect(clampScore(12, 10)).toBe(10);
    expect(clampScore(7.456, 10)).toBe(7.46);
  });

  it("computes percentage", () => {
    expect(computePercentage(28, 40)).toBe(70);
    expect(computePercentage(1, 0)).toBe(0);
  });

  it("prefers final approved score", () => {
    expect(resolveDisplayScore(3, 2)).toBe(2);
    expect(resolveDisplayScore(3, null)).toBe(3);
  });

  it("sums scores", () => {
    expect(sumScores([1, 2, 3])).toBe(6);
  });
});
