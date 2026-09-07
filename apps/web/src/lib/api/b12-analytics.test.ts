import { afterEach, describe, expect, it, vi } from "vitest";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { HybridEduVijnaApi } from "@/lib/api/hybrid/adapter";
import {
  b12RebuildApiToView,
  masteryStateApiToView,
  masteryTrendApiToView,
  mistakeNotebookApiToView,
  recoverableMarksApiToView,
  repeatedErrorsApiToView,
  type B12MasteryStateDto,
  type B12MasteryTrendDto,
  type B12MistakeNotebookDto,
  type B12RecoverableMarksDto,
  type B12RepeatedErrorsDto,
  type B12RebuildResultDto,
} from "@/lib/api/http/analytics";
import { ApiError } from "@/lib/api/http/errors";
import {
  B12_RECOVERABLE_MARKS_DISCLAIMER,
  formatMasteryRatio,
} from "@/lib/types/domain";

const masteryStateDto: B12MasteryStateDto = {
  student_id: "33333333-3333-4333-8333-333333333333",
  items: [
    {
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      curriculum_node_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      curriculum_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      code: "ALG",
      title: "Algebra",
      node_type: "TOPIC",
      concept_mastery: "0.75",
      execution_accuracy: null,
      concept_decisive_count: 4,
      execution_decisive_count: 0,
      concept_inconclusive_count: 1,
      execution_inconclusive_count: 2,
      evidence_count: 5,
      insufficient_concept_evidence: false,
      insufficient_execution_evidence: true,
      source_evidence_hash: "hash-1",
      algorithm_version: "B12_V1",
      last_updated_at: "2026-09-07T00:00:00Z",
    },
  ],
  algorithm_version: "B12_V1",
  source: "MASTERY_EVIDENCE",
  as_of: "2026-09-07T00:00:00Z",
};

const masteryTrendDto: B12MasteryTrendDto = {
  student_id: "33333333-3333-4333-8333-333333333333",
  curriculum_node_id: null,
  points: [
    {
      curriculum_node_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      curriculum_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      code: "ALG",
      title: "Algebra",
      published_result_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      assessment_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      assessment_code: "MT-1",
      effective_at: "2026-08-01T00:00:00Z",
      concept_mastery: 0.5,
      execution_accuracy: 0.25,
      concept_decisive_count: 2,
      execution_decisive_count: 2,
      evidence_count: 2,
      insufficient_concept_evidence: false,
      insufficient_execution_evidence: false,
      source_evidence_hash: "hash-t1",
      algorithm_version: "B12_V1",
    },
  ],
  algorithm_version: "B12_V1",
  source: "MASTERY_EVIDENCE",
  as_of: "2026-09-07T00:00:00Z",
};

const repeatedDto: B12RepeatedErrorsDto = {
  student_id: "33333333-3333-4333-8333-333333333333",
  items: [
    {
      error_code: "CALCULATION",
      occurrence_count: 3,
      distinct_published_result_count: 2,
      distinct_assessment_count: 2,
      first_seen_at: "2026-08-01T00:00:00Z",
      last_seen_at: "2026-09-01T00:00:00Z",
      affected_question_evaluations: [],
      curriculum_node_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    },
  ],
  recurrence_threshold: 2,
  algorithm_version: "B12_V1",
  source: "MASTERY_EVIDENCE",
  as_of: "2026-09-07T00:00:00Z",
};

const recoverableDto: B12RecoverableMarksDto = {
  student_id: "33333333-3333-4333-8333-333333333333",
  total_lost_marks: "5.00",
  attributed_potentially_recoverable_marks: "3.50",
  unattributed_lost_marks: "1.50",
  items: [
    {
      error_code: "CALCULATION",
      potentially_recoverable_marks: "3.50",
      occurrence_count: 2,
      percent_of_total_lost: "70.0",
      affected_references: [],
    },
  ],
  disclaimer: B12_RECOVERABLE_MARKS_DISCLAIMER,
  algorithm_version: "B12_V1",
  source: "PUBLISHED_LEDGER",
  as_of: "2026-09-07T00:00:00Z",
};

const notebookDto: B12MistakeNotebookDto = {
  student_id: "33333333-3333-4333-8333-333333333333",
  entries: [
    {
      id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
      published_result_id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      assessment_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      assessment_code: "MT-1",
      submission_id: "11111111-1111-4111-8111-111111111111",
      question_evaluation_id: "22222222-2222-4222-8222-222222222222",
      question_version_id: "33333333-3333-4333-8333-333333333334",
      question_code: "Q1",
      academic_error_code: "CALCULATION",
      final_score: "2.00",
      max_mark: "5.00",
      deduction_reasons: ["Arithmetic slip"],
      first_divergence_step: "1",
      curriculum_nodes: [
        {
          id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          code: "ALG",
          title: "Algebra",
          node_type: "TOPIC",
        },
      ],
      recommended_practice_kind: "EXECUTION_PRACTICE",
      linked_learning_recommendation_ids: [
        "44444444-4444-4444-8444-444444444444",
      ],
      source_ledger_snapshot_hash: "ledger-hash",
      algorithm_version: "B12_V1",
      materialized_at: "2026-09-07T00:00:00Z",
      effective_at: "2026-08-01T00:00:00Z",
    },
  ],
  algorithm_version: "B12_V1",
  source: "PUBLISHED_LEDGER",
  as_of: "2026-09-07T00:00:00Z",
};

const rebuildDto: B12RebuildResultDto = {
  student_id: "33333333-3333-4333-8333-333333333333",
  algorithm_version: "B12_V1",
  mastery_state_count: 1,
  snapshot_count: 2,
  notebook_entry_count: 1,
  source_evidence_hash: "rebuild-hash",
  source: "MASTERY_EVIDENCE",
};

const emptyMasteryStateDto: B12MasteryStateDto = {
  student_id: "33333333-3333-4333-8333-333333333333",
  items: [],
  algorithm_version: "B12_V1",
  source: "MASTERY_EVIDENCE",
  as_of: "2026-09-07T00:00:00Z",
};

describe("B12 mastery ratio helper", () => {
  it("labels null as insufficient evidence (longitudinal, not B8 signal)", () => {
    expect(formatMasteryRatio(null)).toBe("Insufficient evidence");
    expect(formatMasteryRatio(0.75)).toBe("75%");
  });
});

describe("B12 analytics mappers", () => {
  it("maps mastery state with null execution and insufficient flags", () => {
    const view = masteryStateApiToView(masteryStateDto);
    expect(view.source).toBe("MASTERY_EVIDENCE");
    expect(view.algorithm_version).toBe("B12_V1");
    expect(view.items[0]?.concept_mastery).toBe(0.75);
    expect(view.items[0]?.execution_accuracy).toBeNull();
    expect(view.items[0]?.insufficient_execution_evidence).toBe(true);
    expect(JSON.stringify(view)).not.toMatch(/resource_assignment/);
    expect(JSON.stringify(view)).not.toMatch(/open.?web/i);
  });

  it("maps empty mastery state without inventing priors", () => {
    const view = masteryStateApiToView(emptyMasteryStateDto);
    expect(view.items).toEqual([]);
  });

  it("maps mastery trend points", () => {
    const view = masteryTrendApiToView(masteryTrendDto);
    expect(view.points).toHaveLength(1);
    expect(view.points[0]?.assessment_code).toBe("MT-1");
    expect(view.source).toBe("MASTERY_EVIDENCE");
  });

  it("maps repeated errors without review codes in fixture", () => {
    const view = repeatedErrorsApiToView(repeatedDto);
    expect(view.items[0]?.error_code).toBe("CALCULATION");
    expect(view.recurrence_threshold).toBe(2);
    expect(JSON.stringify(view)).not.toMatch(/UNREADABLE/);
  });

  it("keeps recoverable marks as decimal strings", () => {
    const view = recoverableMarksApiToView(recoverableDto);
    expect(view.total_lost_marks).toBe("5.00");
    expect(view.attributed_potentially_recoverable_marks).toBe("3.50");
    expect(view.items[0]?.potentially_recoverable_marks).toBe("3.50");
    expect(view.items[0]?.percent_of_total_lost).toBe(70);
    expect(view.disclaimer).toContain("analytical estimate");
    expect(view.source).toBe("PUBLISHED_LEDGER");
  });

  it("maps mistake notebook without resource assignment fields", () => {
    const view = mistakeNotebookApiToView(notebookDto);
    expect(view.entries[0]?.academic_error_code).toBe("CALCULATION");
    expect(view.entries[0]?.final_score).toBe("2.00");
    expect(view.entries[0]?.max_mark).toBe("5.00");
    expect(view.entries[0]?.linked_learning_recommendation_ids).toHaveLength(1);
    expect(JSON.stringify(view)).not.toMatch(/resource_url/);
    expect(JSON.stringify(view)).not.toMatch(/assign_resource/);
    expect(JSON.stringify(view)).not.toMatch(/open_web/);
  });

  it("maps B12 rebuild result", () => {
    const view = b12RebuildApiToView(rebuildDto);
    expect(view.mastery_state_count).toBe(1);
    expect(view.notebook_entry_count).toBe(1);
    expect(view.source).toBe("MASTERY_EVIDENCE");
  });
});

describe("B12 hybrid routing", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("routes mastery-state to live HTTP without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    expect(getApiCapabilities().analytics).toBe("live");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(masteryStateDto), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await HybridEduVijnaApi.getStudentMasteryState(
      "33333333-3333-4333-8333-333333333333",
    );

    expect(result.items[0]?.code).toBe("ALG");
    const url = String(fetchMock.mock.calls[0]?.[0]);
    expect(url).toContain("/mastery-state");
  });

  it("surfaces live B12 HTTP errors without mock fallback", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "hybrid");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: { code: "NOT_FOUND", message: "Student not found" },
        }),
        { status: 404, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      HybridEduVijnaApi.getStudentMasteryState(
        "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
      ),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("rejects live UUIDs for B12 when analytics is mock", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    expect(getApiCapabilities().analytics).toBe("mock");

    await expect(
      HybridEduVijnaApi.getStudentMasteryState(
        "33333333-3333-4333-8333-333333333333",
      ),
    ).rejects.toMatchObject({ code: "B12_MOCK_DEMO_ONLY" });

    await expect(
      HybridEduVijnaApi.getStudentRepeatedErrors(
        "33333333-3333-4333-8333-333333333333",
      ),
    ).rejects.toMatchObject({ code: "B12_MOCK_DEMO_ONLY" });
  });

  it("serves demo student B12 fixtures in mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    const state = await HybridEduVijnaApi.getStudentMasteryState(
      "student-demo-001",
    );
    expect(state.items.length).toBeGreaterThan(0);
    expect(state.source).toBe("MASTERY_EVIDENCE");

    const repeated = await HybridEduVijnaApi.getStudentRepeatedErrors(
      "student-demo-001",
    );
    expect(repeated.items[0]?.error_code).toBe("CALCULATION");

    const recoverable = await HybridEduVijnaApi.getStudentRecoverableMarks(
      "student-demo-001",
    );
    expect(recoverable.disclaimer).toContain("analytical estimate");
    expect(typeof recoverable.total_lost_marks).toBe("string");

    const notebook = await HybridEduVijnaApi.getStudentMistakeNotebook(
      "student-demo-001",
    );
    expect(notebook.entries.length).toBeGreaterThan(0);
    expect(JSON.stringify(notebook)).not.toMatch(/resource_assignment/);
  });

  it("does not expose rebuild in mock mode", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_MODE", "mock");
    await expect(
      HybridEduVijnaApi.rebuildStudentB12!("student-demo-001"),
    ).rejects.toMatchObject({ code: "ANALYTICS_NOT_LIVE" });
  });
});
