import { describe, expect, it } from "vitest";
import {
  canFinalizeTranscriptionWorkspace,
  isTranscriptionReviewComplete,
} from "@/lib/transcription/finalize-eligibility";

describe("transcription finalize eligibility", () => {
  it("treats review as incomplete when reviewed < required", () => {
    expect(isTranscriptionReviewComplete(0, 1)).toBe(false);
    expect(isTranscriptionReviewComplete(1, 2)).toBe(false);
    expect(canFinalizeTranscriptionWorkspace(0, 1, false)).toBe(false);
    expect(canFinalizeTranscriptionWorkspace(1, 2, false)).toBe(false);
  });

  it("allows finalize when reviewed === required and not busy", () => {
    expect(isTranscriptionReviewComplete(1, 1)).toBe(true);
    expect(canFinalizeTranscriptionWorkspace(1, 1, false)).toBe(true);
    expect(canFinalizeTranscriptionWorkspace(2, 2, false)).toBe(true);
  });

  it("blocks finalize while a mutation is busy even when review is complete", () => {
    expect(canFinalizeTranscriptionWorkspace(1, 1, true)).toBe(false);
  });
});
