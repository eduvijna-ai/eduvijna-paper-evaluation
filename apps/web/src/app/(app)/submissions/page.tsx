"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function SubmissionsPage() {
  const router = useRouter();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["submissions"],
    queryFn: () => api.listSubmissions(),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="submissions-page">
      <PageHeader
        title="Submissions"
        description="Track pipeline state from upload through published results."
        breadcrumbs={[{ label: "Submissions" }]}
        actions={
          <Link
            href="/submissions/upload"
            data-testid="upload-submission-link"
            className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
          >
            Upload papers
          </Link>
        }
      />
      <DataTable
        data-testid="submissions-table"
        rows={data}
        onRowClick={(row) => router.push(`/submissions/${row.id}`)}
        columns={[
          {
            key: "student",
            header: "Student",
            cell: (r) => r.student_display_name ?? "Unresolved",
          },
          {
            key: "identity",
            header: "Identity",
            cell: (r) => (
              <StatusBadge kind="identity" state={r.student_match_state} />
            ),
          },
          {
            key: "state",
            header: "Pipeline",
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
    </div>
  );
}
