import { describe, expect, it } from "vitest";
import { assertApiModeAllowed } from "./client";

describe("assertApiModeAllowed production mock guard", () => {
  it("allows mock outside production", () => {
    expect(() =>
      assertApiModeAllowed("mock", { nodeEnv: "development" }),
    ).not.toThrow();
    expect(() =>
      assertApiModeAllowed("mock", { nodeEnv: "test" }),
    ).not.toThrow();
  });

  it("allows hybrid in production", () => {
    expect(() =>
      assertApiModeAllowed("hybrid", { nodeEnv: "production" }),
    ).not.toThrow();
  });

  it("refuses mock in production", () => {
    expect(() =>
      assertApiModeAllowed("mock", { nodeEnv: "production" }),
    ).toThrow(/forbidden in production/i);
  });

  it("allows explicit escape hatch for emergency mock in production", () => {
    expect(() =>
      assertApiModeAllowed("mock", {
        nodeEnv: "production",
        allowProductionMock: "1",
      }),
    ).not.toThrow();
  });
});
