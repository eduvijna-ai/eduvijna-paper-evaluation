"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function OperationsModerationPage() {
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const casesQuery = useQuery({
    queryKey: ["b16-moderation-cases"],
    queryFn: () => api.listModerationCases!(),
  });

  const decideMutation = useMutation({
    mutationFn: (input: {
      caseId: string;
      decision: "APPROVE" | "RETURN" | "REJECT";
      reason?: string;
    }) =>
      api.decideModerationCase!(input.caseId, {
        decision: input.decision,
        reason: input.reason,
      }),
    onSuccess: () => {
      setReason("");
      void queryClient.invalidateQueries({ queryKey: ["b16-moderation-cases"] });
    },
  });

  if (casesQuery.isLoading) return <LoadingState label="Loading moderation…" />;
  if (casesQuery.isError) {
    return <ErrorState title="Could not load moderation cases" />;
  }

  const cases = casesQuery.data?.items ?? [];
  const activeId = selectedId ?? cases[0]?.id ?? null;
  const active = cases.find((c) => c.id === activeId) ?? null;

  return (
    <div data-testid="b16-moderation-workspace" className="space-y-6">
      <PageHeader
        title="Moderation"
        description="Multi-stage approval of evaluator work."
      />
      <div className="grid gap-4 lg:grid-cols-[1fr_1.2fr]">
        <div data-testid="b16-moderation-list" className="space-y-2">
          {cases.map((row) => (
            <button
              key={row.id}
              type="button"
              data-testid="b16-moderation-row"
              onClick={() => setSelectedId(row.id)}
              className={`w-full rounded-lg border px-3 py-2 text-left text-sm ${
                row.id === activeId
                  ? "border-teal-300 bg-teal-50"
                  : "border-slate-200 bg-white"
              }`}
            >
              <div className="font-medium">{row.submission_id}</div>
              <div data-testid="b16-moderation-status" className="text-xs text-slate-500">
                {row.status} · stage {row.current_stage_order}
              </div>
            </button>
          ))}
        </div>
        {active ? (
          <div
            data-testid="b16-moderation-detail"
            className="rounded-lg border border-slate-200 bg-white p-4"
          >
            <div className="text-sm font-medium">Case {active.id}</div>
            <div className="mt-2 text-xs text-slate-500">
              Status {active.status} · stage {active.current_stage_order}
            </div>
            <label className="mt-4 block text-xs font-medium text-slate-600">
              Reason (required for RETURN/REJECT)
              <textarea
                data-testid="b16-moderation-reason"
                className="mt-1 w-full rounded-md border border-slate-200 p-2 text-sm"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={3}
              />
            </label>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                data-testid="b16-moderation-approve"
                className="rounded-md bg-teal-700 px-3 py-1.5 text-xs text-white"
                onClick={() =>
                  decideMutation.mutate({
                    caseId: active.id,
                    decision: "APPROVE",
                  })
                }
              >
                Approve
              </button>
              <button
                type="button"
                data-testid="b16-moderation-return"
                className="rounded-md border border-slate-200 px-3 py-1.5 text-xs"
                onClick={() =>
                  decideMutation.mutate({
                    caseId: active.id,
                    decision: "RETURN",
                    reason,
                  })
                }
              >
                Return
              </button>
              <button
                type="button"
                data-testid="b16-moderation-reject"
                className="rounded-md border border-rose-200 px-3 py-1.5 text-xs text-rose-700"
                onClick={() =>
                  decideMutation.mutate({
                    caseId: active.id,
                    decision: "REJECT",
                    reason,
                  })
                }
              >
                Reject
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
