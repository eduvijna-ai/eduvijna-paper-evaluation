import { describe, expect, it } from "vitest";

import {
  getGuardianPanelState,
  shouldLoadStudentGuardians,
} from "./guardian-panel-state";

describe("guardian panel permission state", () => {
  it("does not load guardians when guardian:read is absent", () => {
    expect(shouldLoadStudentGuardians(false)).toBe(false);
    expect(
      getGuardianPanelState({
        canRead: false,
        isLoading: false,
        isError: false,
        guardianCount: 0,
      }),
    ).toBe("restricted");
  });

  it("shows the real empty state only after a readable query succeeds", () => {
    expect(shouldLoadStudentGuardians(true)).toBe(true);
    expect(
      getGuardianPanelState({
        canRead: true,
        isLoading: false,
        isError: false,
        guardianCount: 0,
      }),
    ).toBe("empty");
  });

  it("keeps guardian API failures distinct from an empty result", () => {
    expect(
      getGuardianPanelState({
        canRead: true,
        isLoading: false,
        isError: true,
        guardianCount: 0,
      }),
    ).toBe("error");
  });

  it("reports ready when readable guardians were returned", () => {
    expect(
      getGuardianPanelState({
        canRead: true,
        isLoading: false,
        isError: false,
        guardianCount: 2,
      }),
    ).toBe("ready");
  });
});
