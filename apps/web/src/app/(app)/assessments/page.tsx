"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, isApiError } from "@/lib/api";
import { A2_PERMISSIONS } from "@/lib/api/a2-types";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { getSession, hasPermission } from "@/lib/auth/session";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function AssessmentsPage() {
  const router = useRouter();
  const capabilities = getApiCapabilities();
  const initialSession = useMemo(() => getSession(), []);
  const [session, setSession] = useState(initialSession);
  useEffect(() => setSession(getSession()), []);
  const canManage = hasPermission(session, A2_PERMISSIONS.assessmentManage);
  const canCreate = capabilities.assessments === "mock" || canManage;

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["assessments"],
    queryFn: () => api.listAssessments(),
  });

  if (isLoading) {
    return (
      <div data-testid="assessments-page">
        <LoadingState />
      </div>
    );
  }
  if (isError || !data) {
    if (isApiError(error) && error.kind === "forbidden") {
      return (
        <div data-testid="assessments-page">
          <ErrorState
            title="Permission denied"
            message="You do not have assessment:read permission."
          />
        </div>
      );
    }
    return (
      <div data-testid="assessments-page">
        <ErrorState onRetry={() => void refetch()} />
      </div>
    );
  }

  return (
    <div data-testid="assessments-page">
      <PageHeader
        title="Assessments"
        description="Create, review rubrics, and manage assessment lifecycle."
        breadcrumbs={[{ label: "Assessments" }]}
        actions={
          canCreate ? (
            <Link
              href="/assessments/new"
              data-testid="new-assessment-link"
              className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
            >
              New assessment
            </Link>
          ) : undefined
        }
      />
      <DataTable
        data-testid="assessments-table"
        rows={data}
        onRowClick={(row) => router.push(`/assessments/${row.id}`)}
        columns={[
          { key: "code", header: "Code", cell: (r) => r.code },
          { key: "title", header: "Title", cell: (r) => r.title },
          { key: "curriculum", header: "Curriculum", cell: (r) => r.subject },
          {
            key: "state",
            header: "State",
            cell: (r) => (
              <StatusBadge kind="assessment" state={r.workflow_state} />
            ),
          },
          {
            key: "marks",
            header: "Marks",
            cell: (r) => r.max_marks,
          },
        ]}
      />
    </div>
  );
}
