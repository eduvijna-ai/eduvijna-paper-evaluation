import { describe, expect, it } from "vitest";
import { paperViewerStatusLabel } from "@/components/paper/PaperViewerShell";

describe("paperViewerStatusLabel", () => {
  it("never says Synthetic · no PDFs in live mode", () => {
    expect(
      paperViewerStatusLabel({ mode: "live", imageStatus: "loading" }),
    ).toBe("Loading page image…");
    expect(
      paperViewerStatusLabel({
        mode: "live",
        pageImageUrl: "blob:x",
        imageStatus: "ready",
      }),
    ).toBe("Live page image");
    expect(
      paperViewerStatusLabel({ mode: "live", imageStatus: "error" }),
    ).toBe("Page image unavailable");
    expect(paperViewerStatusLabel({ mode: "live" })).toBe(
      "Loading page image…",
    );
    expect(paperViewerStatusLabel({ mode: "live" })).not.toMatch(/Synthetic/i);
  });

  it("labels synthetic/mock sketch without the old Synthetic · no PDFs string", () => {
    expect(paperViewerStatusLabel({ mode: "synthetic" })).toBe(
      "Mock sketch (no live PDF)",
    );
  });

  it("prefers draw mode when enabled", () => {
    expect(
      paperViewerStatusLabel({
        mode: "live",
        pageImageUrl: "blob:x",
        drawEnabled: true,
      }),
    ).toBe("Draw mode");
  });
});
