import { describe, expect, it, vi } from "vitest";
import { clientRectToNormalizedBBox } from "@/components/paper/PaperViewerShell";

describe("clientRectToNormalizedBBox", () => {
  it("normalizes client drag coords against page getBoundingClientRect", () => {
    const pageEl = {
      getBoundingClientRect: () => ({
        left: 100,
        top: 50,
        width: 200,
        height: 400,
        right: 300,
        bottom: 450,
        x: 100,
        y: 50,
        toJSON: () => ({}),
      }),
    } as unknown as HTMLElement;

    expect(
      clientRectToNormalizedBBox(
        pageEl,
        { x: 120, y: 90 },
        { x: 180, y: 170 },
      ),
    ).toEqual({
      x: 0.1,
      y: 0.1,
      width: 0.3,
      height: 0.2,
    });
  });

  it("clamps out-of-bounds drags and orders min/max corners", () => {
    const pageEl = {
      getBoundingClientRect: () => ({
        left: 0,
        top: 0,
        width: 100,
        height: 100,
        right: 100,
        bottom: 100,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      }),
    } as unknown as HTMLElement;

    expect(
      clientRectToNormalizedBBox(
        pageEl,
        { x: 120, y: 80 },
        { x: -10, y: 20 },
      ),
    ).toEqual({
      x: 0,
      y: 0.2,
      width: 1,
      height: 0.6,
    });
  });

  it("uses visual bounding rect so CSS zoom is accounted for", () => {
    // Simulate a page that was CSS-scaled: getBoundingClientRect already
    // reflects the visual size — callers must not reverse the transform.
    const getBoundingClientRect = vi.fn(() => ({
      left: 10,
      top: 20,
      width: 400,
      height: 200,
      right: 410,
      bottom: 220,
      x: 10,
      y: 20,
      toJSON: () => ({}),
    }));
    const pageEl = { getBoundingClientRect } as unknown as HTMLElement;

    const bbox = clientRectToNormalizedBBox(
      pageEl,
      { x: 10, y: 20 },
      { x: 210, y: 120 },
    );
    expect(getBoundingClientRect).toHaveBeenCalled();
    expect(bbox).toEqual({ x: 0, y: 0, width: 0.5, height: 0.5 });
  });
});
