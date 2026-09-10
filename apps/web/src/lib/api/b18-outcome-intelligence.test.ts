import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { OutcomeIntelligenceHttpApi } from "@/lib/api/http/outcome_intelligence";
import {
  ANSWER_CLUSTER_DEMO_ID,
  ANSWER_CLUSTER_RUN_DEMO_ID,
  OUTCOME_ATTAINMENT_REPORT_DEMO_ID,
  OUTCOME_DEFINITION_CO_DEMO_ID,
} from "@/lib/api/mock/data";
import { MockEduVijnaApi } from "@/lib/api/mock/adapter";
import {
  ANSWER_CLUSTER_RUN_STATUSES,
  OUTCOME_MAPPING_SET_STATUSES,
  OUTCOME_TYPES,
} from "@/lib/types/enums";

describe("B18 enums", () => {
  it("includes clustering and outcome statuses", () => {
    expect(ANSWER_CLUSTER_RUN_STATUSES).toContain("COMPLETED");
    expect(OUTCOME_TYPES).toEqual(["CO", "PO"]);
    expect(OUTCOME_MAPPING_SET_STATUSES).toContain("ACTIVE");
  });
});

describe("B18 mock outcome intelligence", () => {
  it("lists cluster runs and cluster detail with members", async () => {
    const runs = await MockEduVijnaApi.listAnswerClusterRuns!();
    expect(
      runs.items.some((r) => r.id === ANSWER_CLUSTER_RUN_DEMO_ID),
    ).toBe(true);
    const clusters = await MockEduVijnaApi.listAnswerClusters!(
      ANSWER_CLUSTER_RUN_DEMO_ID,
    );
    expect(clusters.items.length).toBeGreaterThan(0);
    const detail = await MockEduVijnaApi.getAnswerCluster!(
      ANSWER_CLUSTER_DEMO_ID,
    );
    expect(detail.members.length).toBeGreaterThan(0);
  });

  it("lists outcome definitions and attainment report metrics", async () => {
    const defs = await MockEduVijnaApi.listOutcomeDefinitions!();
    expect(
      defs.items.some((d) => d.id === OUTCOME_DEFINITION_CO_DEMO_ID),
    ).toBe(true);
    const report = await MockEduVijnaApi.getOutcomeAttainmentReport!(
      OUTCOME_ATTAINMENT_REPORT_DEMO_ID,
    );
    expect(report.metrics?.length).toBeGreaterThan(0);
    expect(report.metrics?.[0].attainment_pct).toBe(60);
  });

  it("exports attainment report CSV", async () => {
    const csv = await MockEduVijnaApi.exportOutcomeAttainmentReportCsv!(
      OUTCOME_ATTAINMENT_REPORT_DEMO_ID,
    );
    expect(csv).toContain("outcome_type,outcome_code");
    expect(csv).toContain("CO1");
  });
});

describe("B18 hybrid routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("routes listAnswerClusterRuns to HTTP in hybrid", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(getApiCapabilities().quality).toBe("live");
    const spy = vi
      .spyOn(OutcomeIntelligenceHttpApi, "listAnswerClusterRuns")
      .mockResolvedValue({ items: [] });
    await HybridEduVijnaApi.listAnswerClusterRuns!();
    expect(spy).toHaveBeenCalledOnce();
  });

  it("routes listOutcomeAttainmentReports to HTTP in hybrid", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const spy = vi
      .spyOn(OutcomeIntelligenceHttpApi, "listOutcomeAttainmentReports")
      .mockResolvedValue({ items: [] });
    await HybridEduVijnaApi.listOutcomeAttainmentReports!();
    expect(spy).toHaveBeenCalledOnce();
  });
});
