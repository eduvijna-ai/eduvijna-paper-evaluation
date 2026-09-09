"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function OperationsGradingPage() {
  const poolsQuery = useQuery({
    queryKey: ["b16-grading-pools"],
    queryFn: () => api.listGradingPools!(),
  });

  if (poolsQuery.isLoading) return <LoadingState label="Loading grading pools…" />;
  if (poolsQuery.isError) {
    return <ErrorState title="Could not load grading pools" />;
  }

  const pools = poolsQuery.data?.items ?? [];

  return (
    <div data-testid="b16-grading-workspace" className="space-y-6">
      <PageHeader
        title="Horizontal grading"
        description="Manage evaluator pools, allocation, and progress."
      />
      <div className="flex flex-wrap gap-3 text-sm">
        <Link
          href="/operations/grading/my-queue"
          data-testid="b16-link-my-queue"
          className="text-teal-700 underline"
        >
          My grading queue
        </Link>
        <Link href="/operations/moderation" className="text-teal-700 underline">
          Moderation
        </Link>
        <Link href="/operations/grievances" className="text-teal-700 underline">
          Grievances
        </Link>
      </div>
      <div data-testid="b16-pool-list" className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-slate-600">
            <tr>
              <th className="px-3 py-2 font-medium">Pool</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Strategy</th>
              <th className="px-3 py-2 font-medium">Members</th>
            </tr>
          </thead>
          <tbody>
            {pools.map((pool) => (
              <tr
                key={pool.id}
                data-testid="b16-pool-row"
                className="border-t border-slate-100"
              >
                <td className="px-3 py-2 font-mono text-xs">{pool.id}</td>
                <td className="px-3 py-2" data-testid="b16-pool-status">
                  {pool.status}
                </td>
                <td className="px-3 py-2">{pool.allocation_strategy}</td>
                <td className="px-3 py-2">{pool.member_count ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
