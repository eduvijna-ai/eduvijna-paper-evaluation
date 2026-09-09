import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import { OperationsHttpApi } from "@/lib/api/http/operations";
import {
  GRADING_POOL_DEMO_ID,
  GRADING_WORK_DEMO_ID,
  GRIEVANCE_DEMO_ID,
  MODERATION_CASE_DEMO_ID,
} from "@/lib/api/mock/data";
import { MockEduVijnaApi } from "@/lib/api/mock/adapter";
import {
  GRADING_POOL_STATUSES,
  GRADING_WORK_ITEM_STATUSES,
  GRIEVANCE_STATUSES,
  MODERATION_CASE_STATUSES,
  PUBLICATION_STATUSES,
  SUBMISSION_STATES,
} from "@/lib/types/enums";

describe("B16 enums", () => {
  it("includes MODERATION_REVIEW and SUPERSEDED", () => {
    expect(SUBMISSION_STATES).toContain("MODERATION_REVIEW");
    expect(PUBLICATION_STATUSES).toContain("SUPERSEDED");
    expect(GRADING_POOL_STATUSES).toEqual(["DRAFT", "ACTIVE", "CLOSED"]);
    expect(GRADING_WORK_ITEM_STATUSES).toContain("RETURNED");
    expect(MODERATION_CASE_STATUSES).toContain("PENDING");
    expect(GRIEVANCE_STATUSES).toContain("RE_EVALUATING");
  });
});

describe("B16 mock operations", () => {
  it("lists pools, queue, moderation, and grievances", async () => {
    const pools = await MockEduVijnaApi.listGradingPools!();
    expect(pools.items.some((p) => p.id === GRADING_POOL_DEMO_ID)).toBe(true);

    const queue = await MockEduVijnaApi.myGradingQueue!();
    expect(queue.items.some((w) => w.id === GRADING_WORK_DEMO_ID)).toBe(true);

    const started = await MockEduVijnaApi.startGradingWorkItem!(GRADING_WORK_DEMO_ID);
    expect(started.status).toBe("IN_PROGRESS");

    const cases = await MockEduVijnaApi.listModerationCases!();
    expect(cases.items.some((c) => c.id === MODERATION_CASE_DEMO_ID)).toBe(true);

    const grievances = await MockEduVijnaApi.listGrievances!();
    expect(grievances.items.some((g) => g.id === GRIEVANCE_DEMO_ID)).toBe(true);

    const accepted = await MockEduVijnaApi.acceptGrievance!(
      GRIEVANCE_DEMO_ID,
      "Valid",
    );
    expect(accepted.status).toBe("RE_EVALUATING");
    expect(accepted.reevaluation_run_id).toBeTruthy();
  });
});

describe("B16 hybrid routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("marks operations live in hybrid", () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(getApiCapabilities().operations).toBe("live");
  });

  it("routes listGradingPools to HTTP in hybrid", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const spy = vi
      .spyOn(OperationsHttpApi, "listGradingPools")
      .mockResolvedValue({ items: [] });
    await HybridEduVijnaApi.listGradingPools!();
    expect(spy).toHaveBeenCalledOnce();
  });

  it("routes decideModerationCase to HTTP in hybrid", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const spy = vi
      .spyOn(OperationsHttpApi, "decideModerationCase")
      .mockResolvedValue({
        id: "c1",
        policy_id: "p1",
        submission_id: "s1",
        evaluation_run_id: "r1",
        current_stage_order: 1,
        status: "APPROVED",
        created_at: "2026-09-01T00:00:00.000Z",
        updated_at: "2026-09-01T00:00:00.000Z",
      });
    await HybridEduVijnaApi.decideModerationCase!("c1", { decision: "APPROVE" });
    expect(spy).toHaveBeenCalledWith("c1", { decision: "APPROVE" });
  });
});
