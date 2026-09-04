"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatusBadge } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import {
  ErrorState,
  LoadingState,
} from "@/components/ui/FeedbackStates";

export default function DashboardPage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api.getDashboard(),
  });

  if (isLoading) {
    return (
      <div data-testid="dashboard-page">
        <LoadingState />
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div data-testid="dashboard-page">
        <ErrorState onRetry={() => void refetch()} />
      </div>
    );
  }

  return (
    <div data-testid="dashboard-page">
      <PageHeader
        title="Dashboard"
        description="Review queues and recent activity for the Client Validation Build."
        breadcrumbs={[{ label: "Dashboard" }]}
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          {
            label: "Identity review",
            value: data.pending_identity,
            href: "/submissions",
          },
          {
            label: "Mapping review",
            value: data.pending_mapping,
            href: "/submissions",
          },
          {
            label: "Evaluation review",
            value: data.pending_evaluation,
            href: "/submissions",
          },
          {
            label: "Active assessments",
            value: data.active_assessments,
            href: "/assessments",
          },
        ].map((card) => (
          <Link
            key={card.label}
            href={card.href}
            className="rounded-md border border-slate-200 bg-white p-4 hover:border-teal-300"
          >
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
              {card.label}
            </div>
            <div className="mt-2 text-3xl font-semibold tabular-nums text-slate-900">
              {card.value}
            </div>
          </Link>
        ))}
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Recent submissions
          </h2>
          <DataTable
            data-testid="dashboard-submissions"
            rows={data.recent_submissions}
            onRowClick={(row) => {
              window.location.href = `/submissions/${row.id}/evaluation`;
            }}
            columns={[
              {
                key: "student",
                header: "Student",
                cell: (r) => r.student_display_name ?? "Unresolved",
              },
              {
                key: "state",
                header: "State",
                cell: (r) => (
                  <StatusBadge kind="submission" state={r.workflow_state} />
                ),
              },
              {
                key: "assessment",
                header: "Assessment",
                cell: (r) => r.assessment_title,
              },
            ]}
          />
        </section>
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Assessments
          </h2>
          <DataTable
            data-testid="dashboard-assessments"
            rows={data.recent_assessments}
            onRowClick={(row) => {
              window.location.href = `/assessments/${row.id}`;
            }}
            columns={[
              {
                key: "title",
                header: "Title",
                cell: (r) => r.title,
              },
              {
                key: "state",
                header: "State",
                cell: (r) => (
                  <StatusBadge kind="assessment" state={r.workflow_state} />
                ),
              },
              {
                key: "subs",
                header: "Subs",
                cell: (r) => r.submission_count,
              },
            ]}
          />
        </section>
      </div>
    </div>
  );
}
