"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, isApiError } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function CurriculumListPage() {
  const router = useRouter();
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["curricula"],
    queryFn: () => api.listCurricula(),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) {
    if (isApiError(error) && error.kind === "forbidden") {
      return (
        <ErrorState
          title="Permission denied"
          message="You do not have curriculum:read permission."
        />
      );
    }
    return <ErrorState onRetry={() => void refetch()} />;
  }

  return (
    <div data-testid="curriculum-list-page">
      <PageHeader
        title="Curriculum"
        description="Live curriculum structures used for assessment authoring and curriculum mapping."
        breadcrumbs={[{ label: "Curriculum" }]}
      />
      <DataTable
        rows={data}
        onRowClick={(row) => router.push(`/curriculum/${row.id}`)}
        columns={[
          { key: "title", header: "Title", cell: (r) => r.title },
          { key: "code", header: "Code", cell: (r) => r.code },
          { key: "framework", header: "Framework", cell: (r) => r.board },
          { key: "version", header: "Version", cell: (r) => r.grade_label },
          { key: "nodes", header: "Nodes", cell: (r) => r.node_count },
        ]}
      />
    </div>
  );
}
