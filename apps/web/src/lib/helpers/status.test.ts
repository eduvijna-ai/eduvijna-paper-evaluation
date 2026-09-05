import { describe, expect, it } from "vitest";
import { resolveStatusVisual } from "@/lib/helpers/status";

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
});
