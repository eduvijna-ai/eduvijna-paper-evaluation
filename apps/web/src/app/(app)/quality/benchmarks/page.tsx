"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { A1_PERMISSIONS } from "@/lib/api/a1-types";
import { api, isApiError } from "@/lib/api";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type {
  BenchmarkCase,
  BenchmarkDataset,
  BenchmarkRegressionCaseResult,
  BenchmarkRegressionRun,
  BenchmarkVersion,
} from "@/lib/types/domain";

const CANDIDATE_MODELS = [
  "fixed-benchmark-pass",
  "fixed-benchmark-regress",
] as const;

function actionErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "Request failed";
}

function metricValue(metrics: Record<string, unknown>, key: string): string {
  const raw = metrics[key];
  if (raw === null || raw === undefined) return "—";
  if (typeof raw === "number") return Number.isInteger(raw) ? String(raw) : raw.toFixed(3);
  return String(raw);
}

export default function QualityBenchmarksPage() {
  const queryClient = useQueryClient();
  const session = getSession();
  const canManage = hasPermission(session, A1_PERMISSIONS.qualityManage);

  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [datasetForm, setDatasetForm] = useState({
    code: "",
    title: "",
    description: "",
  });
  const [candidateModel, setCandidateModel] =
    useState<(typeof CANDIDATE_MODELS)[number]>("fixed-benchmark-pass");
  const [formError, setFormError] = useState<string | null>(null);

  const datasetsQuery = useQuery({
    queryKey: ["b15-benchmark-datasets"],
    queryFn: () => api.listBenchmarkDatasets!(),
  });

  const datasets = datasetsQuery.data?.items ?? [];
  const activeDatasetId = selectedDatasetId ?? datasets[0]?.id ?? null;

  const versionsQuery = useQuery({
    queryKey: ["b15-benchmark-versions", activeDatasetId],
    queryFn: () => api.listBenchmarkVersions!(activeDatasetId!),
    enabled: Boolean(activeDatasetId),
  });

  const versions = versionsQuery.data?.items ?? [];
  const activeVersionId =
    selectedVersionId && versions.some((v) => v.id === selectedVersionId)
      ? selectedVersionId
      : versions[0]?.id ?? null;
  const activeVersion =
    versions.find((v) => v.id === activeVersionId) ?? null;
  const isDraft = activeVersion?.status === "DRAFT";
  const isLocked = activeVersion?.status === "LOCKED";

  const casesQuery = useQuery({
    queryKey: ["b15-benchmark-cases", activeVersionId],
    queryFn: () => api.listBenchmarkCases!(activeVersionId!),
    enabled: Boolean(activeVersionId),
  });

  const eligibleQuery = useQuery({
    queryKey: ["b15-benchmark-eligible", activeVersionId],
    queryFn: () => api.listBenchmarkEligibleSources!(activeVersionId!),
    enabled: Boolean(activeVersionId) && isDraft,
  });

  const runsQuery = useQuery({
    queryKey: ["b15-benchmark-runs", activeVersionId],
    queryFn: () => api.listBenchmarkRegressionRuns!(activeVersionId!),
    enabled: Boolean(activeVersionId) && isLocked,
  });

  const runs = runsQuery.data?.items ?? [];
  const activeRunId =
    selectedRunId && runs.some((r) => r.id === selectedRunId)
      ? selectedRunId
      : runs[0]?.id ?? null;

  const caseResultsQuery = useQuery({
    queryKey: ["b15-benchmark-case-results", activeRunId],
    queryFn: () => api.listBenchmarkRegressionCaseResults!(activeRunId!),
    enabled: Boolean(activeRunId),
  });

  const gateQuery = useQuery({
    queryKey: ["b15-benchmark-gate", activeRunId],
    queryFn: () => api.getBenchmarkGateVerdict!(activeRunId!),
    enabled: Boolean(activeRunId),
  });

  const activeRun = runs.find((r) => r.id === activeRunId) ?? null;
  const casesById = useMemo(() => {
    const map = new Map<string, BenchmarkCase>();
    for (const c of casesQuery.data?.items ?? []) map.set(c.id, c);
    return map;
  }, [casesQuery.data?.items]);

  const createDatasetMutation = useMutation({
    mutationFn: () => {
      if (!datasetForm.code.trim() || !datasetForm.title.trim()) {
        throw new Error("Code and title are required");
      }
      return api.createBenchmarkDataset!({
        code: datasetForm.code.trim(),
        title: datasetForm.title.trim(),
        description: datasetForm.description.trim() || null,
      });
    },
    onSuccess: (created) => {
      setFormError(null);
      setDatasetForm({ code: "", title: "", description: "" });
      setSelectedDatasetId(created.id);
      void queryClient.invalidateQueries({ queryKey: ["b15-benchmark-datasets"] });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  const createVersionMutation = useMutation({
    mutationFn: () => api.createBenchmarkVersion!(activeDatasetId!),
    onSuccess: (created) => {
      setSelectedVersionId(created.id);
      void queryClient.invalidateQueries({
        queryKey: ["b15-benchmark-versions", activeDatasetId],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  const addCaseMutation = useMutation({
    mutationFn: (input: {
      published_result_id: string;
      question_evaluation_id: string;
    }) => api.addBenchmarkCase!(activeVersionId!, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["b15-benchmark-cases", activeVersionId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["b15-benchmark-versions", activeDatasetId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["b15-benchmark-eligible", activeVersionId],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  const removeCaseMutation = useMutation({
    mutationFn: (caseId: string) =>
      api.removeBenchmarkCase!(activeVersionId!, caseId),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["b15-benchmark-cases", activeVersionId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["b15-benchmark-versions", activeDatasetId],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  const lockMutation = useMutation({
    mutationFn: () => api.lockBenchmarkVersion!(activeVersionId!),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["b15-benchmark-versions", activeDatasetId],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  const startRunMutation = useMutation({
    mutationFn: () =>
      api.startBenchmarkRegressionRun!(activeVersionId!, {
        candidate_provider: "fixed",
        candidate_model: candidateModel,
        candidate_model_version: "B15_V1",
        candidate_prompt_template_version: "fixed-benchmark-v1",
      }),
    onSuccess: (run) => {
      setSelectedRunId(run.id);
      void queryClient.invalidateQueries({
        queryKey: ["b15-benchmark-runs", activeVersionId],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  if (datasetsQuery.isLoading) return <LoadingState />;
  if (datasetsQuery.isError || !datasetsQuery.data) {
    if (
      isApiError(datasetsQuery.error) &&
      datasetsQuery.error.kind === "forbidden"
    ) {
      return (
        <ErrorState
          title="Permission denied"
          message="You do not have quality:read permission for the benchmark workspace."
        />
      );
    }
    return <ErrorState onRetry={() => void datasetsQuery.refetch()} />;
  }

  return (
    <div data-testid="b15-benchmark-workspace">
      <PageHeader
        title="Quality benchmarks"
        description="Curate frozen human-final gold cases and run isolated AI regression gates (B15)."
        breadcrumbs={[{ label: "Quality" }, { label: "Benchmarks" }]}
      />

      {formError ? (
        <p className="mb-4 text-sm text-red-700" role="alert">
          {formError}
        </p>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        <section>
          <h2 className="mb-2 text-sm font-semibold text-slate-800">Datasets</h2>
          <ul
            data-testid="b15-dataset-list"
            className="mb-4 divide-y divide-slate-200 rounded-md border border-slate-200 bg-white"
          >
            {datasets.map((ds: BenchmarkDataset) => (
              <li key={ds.id}>
                <button
                  type="button"
                  data-testid="b15-dataset-row"
                  className={`block w-full px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                    ds.id === activeDatasetId ? "bg-slate-100 font-medium" : ""
                  }`}
                  onClick={() => {
                    setSelectedDatasetId(ds.id);
                    setSelectedVersionId(null);
                    setSelectedRunId(null);
                  }}
                >
                  <span className="block text-slate-900">{ds.code}</span>
                  <span className="block text-xs text-slate-600">{ds.title}</span>
                </button>
              </li>
            ))}
            {datasets.length === 0 ? (
              <li className="px-3 py-2 text-sm text-slate-500">No datasets yet</li>
            ) : null}
          </ul>

          {canManage ? (
            <div
              data-testid="b15-dataset-create"
              className="rounded-md border border-slate-200 bg-white p-3"
            >
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                Create dataset
              </h3>
              <label className="mt-2 block text-xs text-slate-700">
                Code
                <input
                  className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  value={datasetForm.code}
                  onChange={(e) =>
                    setDatasetForm((f) => ({ ...f, code: e.target.value }))
                  }
                />
              </label>
              <label className="mt-2 block text-xs text-slate-700">
                Title
                <input
                  className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  value={datasetForm.title}
                  onChange={(e) =>
                    setDatasetForm((f) => ({ ...f, title: e.target.value }))
                  }
                />
              </label>
              <label className="mt-2 block text-xs text-slate-700">
                Description
                <textarea
                  className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  rows={2}
                  value={datasetForm.description}
                  onChange={(e) =>
                    setDatasetForm((f) => ({
                      ...f,
                      description: e.target.value,
                    }))
                  }
                />
              </label>
              <button
                type="button"
                className="mt-3 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                disabled={createDatasetMutation.isPending}
                onClick={() => createDatasetMutation.mutate()}
              >
                Create
              </button>
            </div>
          ) : null}
        </section>

        <section className="space-y-6">
          <div>
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-slate-800">Versions</h2>
              {canManage && activeDatasetId ? (
                <button
                  type="button"
                  className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-50"
                  disabled={createVersionMutation.isPending}
                  onClick={() => createVersionMutation.mutate()}
                >
                  New draft version
                </button>
              ) : null}
            </div>
            {versionsQuery.isLoading ? (
              <LoadingState />
            ) : (
              <ul
                data-testid="b15-version-list"
                className="divide-y divide-slate-200 rounded-md border border-slate-200 bg-white"
              >
                {versions.map((v: BenchmarkVersion) => (
                  <li key={v.id}>
                    <button
                      type="button"
                      data-testid="b15-version-row"
                      className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                        v.id === activeVersionId ? "bg-slate-100" : ""
                      }`}
                      onClick={() => {
                        setSelectedVersionId(v.id);
                        setSelectedRunId(null);
                      }}
                    >
                      <span>
                        v{v.version_number} · {v.case_count} case
                        {v.case_count === 1 ? "" : "s"}
                      </span>
                      <span
                        data-testid="b15-version-status"
                        className={`rounded px-2 py-0.5 text-xs font-semibold ${
                          v.status === "LOCKED"
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-amber-100 text-amber-900"
                        }`}
                      >
                        {v.status}
                      </span>
                    </button>
                  </li>
                ))}
                {versions.length === 0 ? (
                  <li className="px-3 py-2 text-sm text-slate-500">
                    No versions yet
                  </li>
                ) : null}
              </ul>
            )}
          </div>

          {activeVersionId && isDraft ? (
            <div>
              <h2 className="mb-2 text-sm font-semibold text-slate-800">
                Eligible published sources
              </h2>
              <p className="mb-2 text-xs text-slate-600">
                Sources show published_result_id and question_evaluation_id only
                (no student PII).
              </p>
              <ul
                data-testid="b15-eligible-sources"
                className="space-y-2 rounded-md border border-slate-200 bg-white p-3"
              >
                {(eligibleQuery.data?.items ?? []).flatMap((src) =>
                  src.question_evaluations.map((qe) => (
                    <li
                      key={`${src.published_result_id}-${qe.question_evaluation_id}`}
                      className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-700"
                    >
                      <span>
                        published_result_id={src.published_result_id} ·
                        question_evaluation_id={qe.question_evaluation_id} ·
                        gold marks={qe.final_human_approved_score}/
                        {qe.max_mark}
                      </span>
                      {canManage ? (
                        <button
                          type="button"
                          data-testid="b15-add-case"
                          className="rounded-md border border-slate-300 px-2 py-1 font-medium hover:bg-slate-50 disabled:opacity-50"
                          disabled={addCaseMutation.isPending}
                          onClick={() =>
                            addCaseMutation.mutate({
                              published_result_id: src.published_result_id,
                              question_evaluation_id: qe.question_evaluation_id,
                            })
                          }
                        >
                          Add gold case
                        </button>
                      ) : null}
                    </li>
                  )),
                )}
                {(eligibleQuery.data?.items ?? []).length === 0 ? (
                  <li className="text-sm text-slate-500">
                    No eligible ACCEPTED/OVERRIDDEN published sources
                  </li>
                ) : null}
              </ul>
            </div>
          ) : null}

          {activeVersionId ? (
            <div>
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-slate-800">
                  Gold cases
                </h2>
                {canManage && isDraft ? (
                  <button
                    type="button"
                    data-testid="b15-lock-version"
                    className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                    disabled={
                      lockMutation.isPending ||
                      (casesQuery.data?.items.length ?? 0) < 1
                    }
                    onClick={() => lockMutation.mutate()}
                  >
                    Lock version
                  </button>
                ) : null}
              </div>
              <ul className="divide-y divide-slate-200 rounded-md border border-slate-200 bg-white">
                {(casesQuery.data?.items ?? []).map((c) => (
                  <li
                    key={c.id}
                    data-testid="b15-case-row"
                    className="flex flex-wrap items-start justify-between gap-3 px-3 py-2 text-sm"
                  >
                    <div>
                      <div className="font-mono text-xs text-slate-600">
                        case={c.id}
                      </div>
                      <div className="text-xs text-slate-600">
                        published_result_id={c.published_result_id}
                      </div>
                      <div className="text-xs text-slate-600">
                        question_evaluation_id={c.question_evaluation_id}
                      </div>
                      <div
                        data-testid="b15-case-gold-marks"
                        className="mt-1 text-sm text-slate-900"
                      >
                        Human gold: {c.expected_final_marks}/
                        {c.expected_max_marks} · codes=
                        {c.expected_error_codes.join(", ") || "none"}
                      </div>
                    </div>
                    {canManage && isDraft ? (
                      <button
                        type="button"
                        data-testid="b15-remove-case"
                        className="rounded-md border border-red-200 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                        disabled={removeCaseMutation.isPending}
                        onClick={() => removeCaseMutation.mutate(c.id)}
                      >
                        Remove
                      </button>
                    ) : null}
                  </li>
                ))}
                {(casesQuery.data?.items ?? []).length === 0 ? (
                  <li className="px-3 py-2 text-sm text-slate-500">
                    No gold cases yet
                  </li>
                ) : null}
              </ul>
            </div>
          ) : null}

          {activeVersionId && isLocked ? (
            <div>
              <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
                <h2 className="text-sm font-semibold text-slate-800">
                  Regression runs
                </h2>
                {canManage ? (
                  <div className="flex flex-wrap items-end gap-2">
                    <label className="block text-xs text-slate-700">
                      Candidate model
                      <select
                        className="mt-1 block rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                        value={candidateModel}
                        onChange={(e) =>
                          setCandidateModel(
                            e.target.value as (typeof CANDIDATE_MODELS)[number],
                          )
                        }
                      >
                        {CANDIDATE_MODELS.map((m) => (
                          <option key={m} value={m}>
                            {m}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      data-testid="b15-start-regression"
                      className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
                      disabled={startRunMutation.isPending}
                      onClick={() => startRunMutation.mutate()}
                    >
                      Start regression
                    </button>
                  </div>
                ) : null}
              </div>

              <ul
                data-testid="b15-run-list"
                className="mb-4 divide-y divide-slate-200 rounded-md border border-slate-200 bg-white"
              >
                {runs.map((run: BenchmarkRegressionRun) => (
                  <li key={run.id}>
                    <button
                      type="button"
                      data-testid="b15-run-row"
                      className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm hover:bg-slate-50 ${
                        run.id === activeRunId ? "bg-slate-100" : ""
                      }`}
                      onClick={() => setSelectedRunId(run.id)}
                    >
                      <span className="font-mono text-xs">{run.id}</span>
                      <span className="text-xs text-slate-600">
                        {run.candidate_model}
                      </span>
                      <span
                        data-testid="b15-run-verdict"
                        className={`rounded px-2 py-0.5 text-xs font-semibold ${
                          run.verdict === "PASS"
                            ? "bg-emerald-100 text-emerald-800"
                            : run.verdict === "FAIL"
                              ? "bg-red-100 text-red-800"
                              : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {run.verdict}
                      </span>
                    </button>
                  </li>
                ))}
                {runs.length === 0 ? (
                  <li className="px-3 py-2 text-sm text-slate-500">
                    No regression runs yet
                  </li>
                ) : null}
              </ul>

              {activeRun ? (
                <>
                  <div
                    data-testid="b15-metrics"
                    className="mb-4 grid gap-2 rounded-md border border-slate-200 bg-white p-3 text-xs sm:grid-cols-2"
                  >
                    <div>
                      exact_score_agreement_rate=
                      {metricValue(
                        activeRun.aggregate_metrics,
                        "exact_score_agreement_rate",
                      )}
                    </div>
                    <div>
                      mean_abs_score_error=
                      {metricValue(
                        activeRun.aggregate_metrics,
                        "mean_abs_score_error",
                      )}
                    </div>
                    <div>
                      taxonomy_agreement_rate=
                      {metricValue(
                        activeRun.aggregate_metrics,
                        "taxonomy_agreement_rate",
                      )}
                    </div>
                    <div>
                      missing_output_rate=
                      {metricValue(
                        activeRun.aggregate_metrics,
                        "missing_output_rate",
                      )}
                    </div>
                  </div>

                  <div
                    data-testid="b15-gate-verdict"
                    className="mb-4 rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                  >
                    Gate:{" "}
                    <strong>
                      {gateQuery.data?.verdict ?? activeRun.verdict}
                    </strong>
                    {gateQuery.data
                      ? ` · passed=${String(gateQuery.data.passed)}`
                      : null}
                  </div>

                  <ul className="space-y-3">
                    {(caseResultsQuery.data?.items ?? []).map(
                      (row: BenchmarkRegressionCaseResult) => {
                        const gold = casesById.get(row.benchmark_case_id);
                        return (
                          <li
                            key={row.id}
                            data-testid="b15-case-diff"
                            className="rounded-md border border-slate-200 bg-white p-3 text-sm"
                          >
                            <div className="mb-2 font-mono text-xs text-slate-600">
                              case={row.benchmark_case_id}
                            </div>
                            <div
                              data-testid="b15-gold-label"
                              className="text-slate-800"
                            >
                              Human gold result: marks=
                              {gold?.expected_final_marks ??
                                String(row.diff.expected_final_marks ?? "—")}
                              · codes=
                              {(
                                gold?.expected_error_codes ??
                                (row.diff.expected_error_codes as
                                  | string[]
                                  | undefined) ??
                                []
                              ).join(", ") || "none"}
                            </div>
                            <div
                              data-testid="b15-candidate-label"
                              className="mt-1 text-slate-800"
                            >
                              Candidate AI output: marks=
                              {row.actual_marks ?? "missing"} · codes=
                              {row.actual_error_codes.join(", ") || "none"} ·
                              abs_error={row.score_abs_error ?? "—"}
                            </div>
                          </li>
                        );
                      },
                    )}
                  </ul>
                </>
              ) : null}
            </div>
          ) : null}
        </section>
      </div>
    </div>
  );
}
