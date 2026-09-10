import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { QualityHttpApi } from "@/lib/api/http/quality";
import {
  CALIBRATION_SESSION_DEMO_ID,
  PSYCHOMETRIC_RUN_DEMO_ID,
} from "@/lib/api/mock/data";
import { MockEduVijnaApi } from "@/lib/api/mock/adapter";
import {
  CALIBRATION_SESSION_STATUSES,
  PSYCHOMETRIC_RUN_STATUSES,
} from "@/lib/types/enums";

describe("B17 enums", () => {
  it("includes psychometric and calibration statuses", () => {
    expect(PSYCHOMETRIC_RUN_STATUSES).toContain("INSUFFICIENT_SAMPLE");
    expect(CALIBRATION_SESSION_STATUSES).toEqual(["DRAFT", "ACTIVE", "CLOSED"]);
  });
});

describe("B17 mock quality", () => {
  it("lists psychometric runs and item metrics", async () => {
    const runs = await MockEduVijnaApi.listPsychometricRuns!();
    expect(runs.items.some((r) => r.id === PSYCHOMETRIC_RUN_DEMO_ID)).toBe(true);
    const items = await MockEduVijnaApi.listPsychometricRunItems!(
      PSYCHOMETRIC_RUN_DEMO_ID,
    );
    expect(items.items.length).toBeGreaterThan(0);
    expect(items.items[0].difficulty_band).toBeTruthy();
  });

  it("lists calibration sessions and blind cases", async () => {
    const sessions = await MockEduVijnaApi.listCalibrationSessions!();
    expect(
      sessions.items.some((s) => s.id === CALIBRATION_SESSION_DEMO_ID),
    ).toBe(true);
    const detail = await MockEduVijnaApi.getCalibrationSession!(
      CALIBRATION_SESSION_DEMO_ID,
    );
    expect(detail.cases?.length).toBeGreaterThan(0);
    const blind = await MockEduVijnaApi.getBlindCalibrationCase!(
      CALIBRATION_SESSION_DEMO_ID,
      detail.cases![0].id,
    );
    expect(blind).not.toHaveProperty("reference_score");
  });
});

describe("B17 hybrid routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("marks quality live in hybrid", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(getApiCapabilities().quality).toBe("live");
  });

  it("routes listPsychometricRuns to HTTP in hybrid", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const spy = vi
      .spyOn(QualityHttpApi, "listPsychometricRuns")
      .mockResolvedValue({ items: [] });
    await HybridEduVijnaApi.listPsychometricRuns!();
    expect(spy).toHaveBeenCalledOnce();
  });

  it("routes listCalibrationSessions to HTTP in hybrid", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const spy = vi
      .spyOn(QualityHttpApi, "listCalibrationSessions")
      .mockResolvedValue({ items: [] });
    await HybridEduVijnaApi.listCalibrationSessions!();
    expect(spy).toHaveBeenCalledOnce();
  });
});
