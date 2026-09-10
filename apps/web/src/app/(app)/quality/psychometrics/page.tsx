"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { A1_PERMISSIONS } from "@/lib/api/a1-types";
import { api, isApiError } from "@/lib/api";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import type { PsychometricRun } from "@/lib/types/domain";

function actionErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message;
  if (error && typeof error === "object" && "message" in error) {
    return String((error as { message: unknown }).message);
  }
  return "Request failed";
}

export default function PsychometricsPage() {
  const queryClient = useQueryClient();
  const session = getSession();
  const canManage = hasPermission(session, A1_PERMISSIONS.qualityManage);
  const [versionId, setVersionId] = useState("");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const uuidLike =
    /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
      versionId.trim(),
    );

  const runsQuery = useQuery({
    queryKey: ["b17-psychometric-runs", versionId],
    queryFn: () =>
      api.listPsychometricRuns!(uuidLike ? versionId.trim() : undefined),
    enabled: versionId.trim() === "" || uuidLike,
  });

  const runs = runsQuery.data?.items ?? [];
  const activeRunId = selectedRunId ?? runs[0]?.id ?? null;

  const itemsQuery = useQuery({
    queryKey: ["b17-psychometric-items", activeRunId],
    queryFn: () => api.listPsychometricRunItems!(activeRunId!),
    enabled: Boolean(activeRunId),
  });

  const createMutation = useMutation({
    mutationFn: () => api.createPsychometricRun!(versionId),
    onSuccess: (run: PsychometricRun) => {
      setFormError(null);
      setSelectedRunId(run.id);
      void queryClient.invalidateQueries({ queryKey: ["b17-psychometric-runs"] });
    },
    onError: (err) => setFormError(actionErrorMessage(err)),
  });

  if (runsQuery.isLoading) return <LoadingState label="Loading psychometrics…" />;
  if (runsQuery.isError) {
    return <ErrorState message={actionErrorMessage(runsQuery.error)} />;
  }

  return (
    <div className="space-y-6" data-testid="b17-psychometrics-workspace">
      <PageHeader
        title="Item psychometrics"
        description="Difficulty and discrimination on published cohorts (PEV-048)."
      />

      <section className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Assessment version ID
          <input
            data-testid="b17-psychometrics-version-input"
            className="rounded border px-2 py-1"
            value={versionId}
            onChange={(e) => setVersionId(e.target.value)}
          />
        </label>
        {canManage ? (
          <button
            type="button"
            data-testid="b17-psychometrics-run"
            className="rounded bg-slate-900 px-3 py-2 text-sm text-white"
            onClick={() => createMutation.mutate()}
            disabled={createMutation.isPending || !versionId}
          >
            Run psychometrics
          </button>
        ) : null}
      </section>
      {formError ? (
        <p className="text-sm text-red-700" data-testid="b17-psychometrics-error">
          {formError}
        </p>
      ) : null}

      <section data-testid="b17-psychometrics-run-list" className="space-y-2">
        <h2 className="text-lg font-medium">Runs</h2>
        {runs.length === 0 ? (
          <p className="text-sm text-slate-600">No runs yet.</p>
        ) : (
          <ul className="divide-y rounded border">
            {runs.map((run) => (
              <li key={run.id}>
                <button
                  type="button"
                  data-testid="b17-psychometrics-run-row"
                  className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm ${
                    activeRunId === run.id ? "bg-slate-100" : ""
                  }`}
                  onClick={() => setSelectedRunId(run.id)}
                >
                  <span>{run.id.slice(0, 12)}…</span>
                  <span data-testid="b17-psychometrics-run-status">
                    {run.status}
                  </span>
                  <span>n={run.source_result_count}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {activeRunId ? (
        <section data-testid="b17-psychometrics-items" className="space-y-2">
          <h2 className="text-lg font-medium">Item metrics</h2>
          {itemsQuery.isLoading ? (
            <LoadingState label="Loading items…" />
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Difficulty</th>
                  <th>Band</th>
                  <th>Discrimination</th>
                  <th>Disc. band</th>
                </tr>
              </thead>
              <tbody>
                {(itemsQuery.data?.items ?? []).map((item) => (
                  <tr key={item.id} data-testid="b17-psychometrics-item-row">
                    <td>{item.question_code}</td>
                    <td>{item.difficulty_index.toFixed(3)}</td>
                    <td data-testid="b17-difficulty-band">
                      {item.difficulty_band ?? "—"}
                    </td>
                    <td>
                      {item.discrimination_index?.toFixed(3) ??
                        item.discrimination_status}
                    </td>
                    <td data-testid="b17-discrimination-band">
                      {item.discrimination_band ?? "—"}
                    </td>
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
