"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function OperationsGrievancesPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [decisionReason, setDecisionReason] = useState("");

  const listQuery = useQuery({
    queryKey: ["b16-grievances"],
    queryFn: () => api.listGrievances!(),
  });

  const acceptMutation = useMutation({
    mutationFn: (id: string) => api.acceptGrievance!(id, decisionReason || null),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["b16-grievances"] }),
  });
  const rejectMutation = useMutation({
    mutationFn: (id: string) => api.rejectGrievance!(id, decisionReason),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["b16-grievances"] }),
  });

  if (listQuery.isLoading) return <LoadingState label="Loading grievances…" />;
  if (listQuery.isError) {
    return <ErrorState title="Could not load grievances" />;
  }

  const items = listQuery.data?.items ?? [];
  const activeId = selectedId ?? items[0]?.id ?? null;
  const active = items.find((g) => g.id === activeId) ?? null;

  return (
    <div data-testid="b16-grievances-workspace" className="space-y-6">
      <PageHeader
        title="Grievances"
        description="Formal re-evaluation requests against published results."
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <div data-testid="b16-grievance-list" className="space-y-2">
          {items.map((row) => (
            <button
              key={row.id}
              type="button"
              data-testid="b16-grievance-row"
              onClick={() => setSelectedId(row.id)}
              className={`w-full rounded-lg border px-3 py-2 text-left text-sm ${
                row.id === activeId
                  ? "border-teal-300 bg-teal-50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <div className="font-medium">{row.requester_reference}</div>
              <div data-testid="b16-grievance-status" className="text-xs text-slate-500">
                {row.status}
              </div>
            </button>
          ))}
        </div>
        {active ? (
          <div
            data-testid="b16-grievance-detail"
            className="rounded-lg border border-slate-200 bg-white p-4 text-sm"
          >
            <div className="font-medium">Grievance {active.id}</div>
            <p className="mt-2 text-slate-600">{active.reason}</p>
            <dl className="mt-4 space-y-1 text-xs text-slate-500">
              <div>
                Original result:{" "}
                <span data-testid="b16-grievance-original">
                  {active.original_published_result_id}
                </span>
              </div>
              <div>
                Re-eval run:{" "}
                <span data-testid="b16-grievance-reeval">
                  {active.reevaluation_run_id ?? "—"}
                </span>
              </div>
              <div>
                Revised result:{" "}
                <span data-testid="b16-grievance-revised">
                  {active.revised_published_result_id ?? "—"}
                </span>
              </div>
            </dl>
            {active.status === "SUBMITTED" || active.status === "UNDER_REVIEW" ? (
              <div className="mt-4 space-y-2">
                <textarea
                  data-testid="b16-grievance-reason"
                  className="w-full rounded-md border border-slate-200 p-2 text-sm"
                  rows={2}
                  value={decisionReason}
                  onChange={(e) => setDecisionReason(e.target.value)}
                  placeholder="Decision reason"
                />
                <div className="flex gap-2">
                  <button
                    type="button"
                    data-testid="b16-grievance-accept"
                    className="rounded-md bg-teal-700 px-3 py-1.5 text-xs text-white"
                    onClick={() => acceptMutation.mutate(active.id)}
                  >
                    Accept
                  </button>
                  <button
                    type="button"
                    data-testid="b16-grievance-reject"
                    className="rounded-md border border-slate-200 px-3 py-1.5 text-xs"
                    onClick={() => rejectMutation.mutate(active.id)}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
