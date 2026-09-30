import { describe, expect, it } from "vitest";
import {
  getSubmissionStatus,
  resolveStatusVisual,
} from "@/lib/helpers/status";

describe("StatusBadge mapping via resolveStatusVisual", () => {
  it("maps assessment ACTIVE to success", () => {
    expect(resolveStatusVisual("assessment", "ACTIVE")).toEqual({
      label: "Active",
      tone: "success",
    });
  });

  it("maps identity REVIEW_REQUIRED to warning", () => {
    expect(resolveStatusVisual("identity", "REVIEW_REQUIRED")).toEqual({
      label: "Review required",
      tone: "warning",
    });
  });

  it("maps submission FAILED to danger", () => {
    expect(resolveStatusVisual("submission", "FAILED")).toEqual({
      label: "Failed",
      tone: "danger",
    });
  });

  it("maps evaluation ACCEPTED to success", () => {
    expect(resolveStatusVisual("evaluation", "ACCEPTED")).toEqual({
      label: "Accepted",
      tone: "success",
    });
  });

  it("labels READY_FOR_EVALUATION as awaiting transcription when not READY", () => {
    expect(
      getSubmissionStatus("READY_FOR_EVALUATION", "REVIEW_REQUIRED"),
    ).toEqual({
      label: "Awaiting transcription",
      tone: "warning",
    });
    expect(
      resolveStatusVisual("submission", "READY_FOR_EVALUATION", {
        transcriptionState: "QUEUED",
      }),
    ).toEqual({
      label: "Awaiting transcription",
      tone: "warning",
    });
  });

  it("keeps Ready for evaluation when transcription is READY", () => {
    expect(getSubmissionStatus("READY_FOR_EVALUATION", "READY")).toEqual({
      label: "Ready for evaluation",
      tone: "info",
    });
  });
});
