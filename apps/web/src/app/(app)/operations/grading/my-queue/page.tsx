"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function MyGradingQueuePage() {
  const queryClient = useQueryClient();
  const queueQuery = useQuery({
    queryKey: ["b16-my-queue"],
    queryFn: () => api.myGradingQueue!(),
  });

  const startMutation = useMutation({
    mutationFn: (id: string) => api.startGradingWorkItem!(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["b16-my-queue"] }),
  });

  if (queueQuery.isLoading) return <LoadingState label="Loading queue…" />;
  if (queueQuery.isError) {
    return <ErrorState title="Could not load grading queue" />;
  }

  const items = queueQuery.data?.items ?? [];

  return (
    <div data-testid="b16-my-queue-workspace" className="space-y-6">
      <PageHeader
        title="My grading queue"
        description="Question-level work assigned to you."
      />
      <Link href="/operations/grading" className="text-sm text-teal-700 underline">
        Back to pools
      </Link>
      <ul data-testid="b16-queue-list" className="space-y-3">
        {items.map((item) => (
          <li
            key={item.id}
            data-testid="b16-queue-item"
            className="rounded-lg border border-slate-200 bg-white p-4"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-medium text-slate-900">
                  QE {item.question_evaluation_id}
                </div>
                <div className="text-xs text-slate-500">
                  Submission {item.submission_id} ·{" "}
                  <span data-testid="b16-queue-status">{item.status}</span>
                </div>
              </div>
              <div className="flex gap-2">
                <Link
                  href={`/submissions/${item.submission_id}/evaluation`}
                  className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs"
                >
                  Open workspace
                </Link>
                {item.status === "QUEUED" || item.status === "RETURNED" ? (
                  <button
                    type="button"
                    data-testid="b16-queue-start"
                    className="rounded-md bg-teal-700 px-2.5 py-1.5 text-xs text-white"
                    onClick={() => startMutation.mutate(item.id)}
                  >
                    Start
                  </button>
                ) : null}
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
