"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { A1_PERMISSIONS } from "@/lib/api/a1-types";
import { api, isApiError } from "@/lib/api";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

function actionErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "Request failed";
}

export default function OutcomeReportingPage() {
  const queryClient = useQueryClient();
  const session = getSession();
  const canManage = hasPermission(session, A1_PERMISSIONS.outcomesManage);
  const canReport = hasPermission(session, A1_PERMISSIONS.outcomesReport);
  const [versionId, setVersionId] = useState("");
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const uuidLike =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const versionOk =
    versionId.trim() === "" || uuidLike.test(versionId.trim());

  const definitionsQuery = useQuery({
    queryKey: ["b18-outcome-definitions"],
    queryFn: () => api.listOutcomeDefinitions!(),
  });

  const mappingSetsQuery = useQuery({
    queryKey: ["b18-outcome-mapping-sets", versionId],
    queryFn: () =>
      api.listOutcomeMappingSets!(versionId.trim() || undefined),
    enabled: versionOk,
  });

  const reportsQuery = useQuery({
    queryKey: ["b18-outcome-attainment-reports", versionId],
    queryFn: () =>
      api.listOutcomeAttainmentReports!(versionId.trim() || undefined),
    enabled: versionOk,
  });

  const reports = reportsQuery.data?.items ?? [];
  const activeReportId = selectedReportId ?? reports[0]?.id ?? null;

  const reportDetailQuery = useQuery({
    queryKey: ["b18-outcome-attainment-report", activeReportId],
    queryFn: () => api.getOutcomeAttainmentReport!(activeReportId!),
    enabled: Boolean(activeReportId),
  });

  const createReportMutation = useMutation({
    mutationFn: () =>
      api.createOutcomeAttainmentReport!({
        assessment_version_id: versionId.trim(),
      }),
    onSuccess: (report) => {
      setFormError(null);
      setSelectedReportId(report.id);
      void queryClient.invalidateQueries({
        queryKey: ["b18-outcome-attainment-reports"],
      });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  return (
    <div className="space-y-6" data-testid="b18-outcomes-workspace">
      <PageHeader
        title="Outcome attainment reporting"
        description="CO/PO mapping and cohort attainment metrics (PEV-051)."
      />
      {definitionsQuery.isLoading || reportsQuery.isLoading ? (
        <LoadingState label="Loading outcome reporting…" />
      ) : null}
      {definitionsQuery.isError ? (
        <ErrorState message={actionErrorMessage(definitionsQuery.error)} />
      ) : null}
      {reportsQuery.isError ? (
        <ErrorState message={actionErrorMessage(reportsQuery.error)} />
      ) : null}

      <section className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Assessment version ID
          <input
            data-testid="b18-outcomes-version-input"
            className="rounded border px-2 py-1"
            value={versionId}
            onChange={(e) => setVersionId(e.target.value)}
          />
        </label>
        {canReport ? (
          <button
            type="button"
            data-testid="b18-outcomes-run-report"
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white"
            onClick={() => createReportMutation.mutate()}
            disabled={createReportMutation.isPending || !versionId}
          >
            Generate attainment report
          </button>
        ) : null}
      </section>
      {formError ? (
        <p className="text-sm text-red-700" data-testid="b18-outcomes-error">
          {formError}
        </p>
      ) : null}

      <section data-testid="b18-outcome-definitions" className="space-y-2">
        <h2 className="text-lg font-medium">Outcome definitions</h2>
        <ul className="divide-y rounded border text-sm">
          {(definitionsQuery.data?.items ?? []).map((def) => (
            <li
              key={def.id}
              data-testid="b18-outcome-definition-row"
              className="flex justify-between px-3 py-2"
            >
              <span>
                <span data-testid="b18-outcome-type">{def.outcome_type}</span>{" "}
                {def.code} — {def.title}
              </span>
              <span>{def.status}</span>
            </li>
          ))}
        </ul>
      </section>

      <section data-testid="b18-outcome-mapping-sets" className="space-y-2">
        <h2 className="text-lg font-medium">Mapping sets</h2>
        <ul className="divide-y rounded border text-sm">
          {(mappingSetsQuery.data?.items ?? []).map((set) => (
            <li
              key={set.id}
              data-testid="b18-outcome-mapping-set-row"
              className="flex justify-between px-3 py-2"
            >
              <span>{set.title}</span>
              <span data-testid="b18-outcome-mapping-set-status">
                {set.status}
              </span>
            </li>
          ))}
        </ul>
        {canManage ? (
          <p className="text-xs text-slate-600">
            Manage mappings via API; demo fixtures include an ACTIVE set.
          </p>
        ) : null}
      </section>

      <section data-testid="b18-outcome-report-list" className="space-y-2">
        <h2 className="text-lg font-medium">Attainment reports</h2>
        {reports.length === 0 ? (
          <p className="text-sm text-slate-600">No reports yet.</p>
        ) : (
          <ul className="divide-y rounded border">
            {reports.map((report) => (
              <li key={report.id}>
                <button
                  type="button"
                  data-testid="b18-outcome-report-row"
                  className={`flex w-full justify-between px-3 py-2 text-left text-sm ${
                    activeReportId === report.id ? "bg-slate-100" : ""
                  }`}
                  onClick={() => setSelectedReportId(report.id)}
                >
                  <span>{report.id.slice(0, 16)}…</span>
                  <span data-testid="b18-outcome-report-status">
                    {report.status}
                  </span>
                  <span>n={report.source_result_count}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {activeReportId && reportDetailQuery.data ? (
        <section data-testid="b18-outcome-metrics" className="space-y-2">
          <h2 className="text-lg font-medium">Attainment metrics</h2>
          {reportDetailQuery.isLoading ? (
            <LoadingState label="Loading metrics…" />
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Code</th>
                  <th>Attainment</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {(reportDetailQuery.data.metrics ?? []).map((metric) => (
                  <tr key={metric.id} data-testid="b18-outcome-metric-row">
                    <td>{metric.outcome_type}</td>
                    <td>{metric.outcome_code}</td>
                    <td data-testid="b18-outcome-attainment-pct">
                      {metric.attainment_pct?.toFixed(1) ?? "—"}%
                    </td>
                    <td>{metric.denom_status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ) : null}
    </div>
  );
}
