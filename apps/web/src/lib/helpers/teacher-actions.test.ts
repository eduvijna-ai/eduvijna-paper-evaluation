import { describe, expect, it } from "vitest";
import { applyTeacherReviewAction } from "./teacher-actions";

describe("teacher review actions", () => {
  it("accepts proposed score", () => {
    const result = applyTeacherReviewAction({
      action: "ACCEPT",
      proposedScore: 2,
      maxMark: 4,
    });
    expect(result.workflow_state).toBe("ACCEPTED");
    expect(result.final_human_approved_score).toBe(2);
    expect(result.requires_followup).toBe(false);
  });

  it("changes score and marks overridden", () => {
    const result = applyTeacherReviewAction({
      action: "CHANGE_SCORE",
      proposedScore: 2,
      maxMark: 4,
      newScore: 3,
      feedback: "Adjusted by teacher",
    });
    expect(result.workflow_state).toBe("OVERRIDDEN");
    expect(result.final_human_approved_score).toBe(3);
  });

  it("awards full marks for valid alternative", () => {
    const result = applyTeacherReviewAction({
      action: "VALID_ALTERNATIVE",
      proposedScore: 1,
      maxMark: 4,
    });
    expect(result.final_human_approved_score).toBe(4);
    expect(result.workflow_state).toBe("OVERRIDDEN");
  });

  it("queues follow-up for mapping and OCR errors", () => {
    expect(
      applyTeacherReviewAction({
        action: "MAPPING_ERROR",
        proposedScore: 1,
        maxMark: 4,
      }).requires_followup,
    ).toBe(true);
    expect(
      applyTeacherReviewAction({
        action: "OCR_TRANSCRIPTION_ERROR",
        proposedScore: 1,
        maxMark: 4,
      }).workflow_state,
    ).toBe("REVIEW_REQUIRED");
  });

  it("escalates to ESCALATED", () => {
    const result = applyTeacherReviewAction({
      action: "ESCALATE",
      proposedScore: 2,
      maxMark: 4,
      feedback: "Needs senior reviewer",
    });
    expect(result.workflow_state).toBe("ESCALATED");
    expect(result.requires_followup).toBe(true);
  });
});
