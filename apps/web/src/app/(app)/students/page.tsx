"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { DataTable } from "@/components/ui/DataTable";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function StudentsPage() {
  const router = useRouter();
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["students"],
    queryFn: () => api.listStudents(),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="students-page">
      <PageHeader
        title="Students"
        description="Demo roster only — synthetic identifiers, no real student PII."
        breadcrumbs={[{ label: "Students" }]}
        actions={
          <Link
            href="/students/import"
            className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
          >
            Import roster
          </Link>
        }
      />
      <DataTable
        rows={data}
        onRowClick={(row) => router.push(`/students/${row.id}`)}
        columns={[
          { key: "roll", header: "Roll", cell: (r) => r.external_ref },
          { key: "name", header: "Name", cell: (r) => r.display_name },
          {
            key: "class",
            header: "Class",
            cell: (r) => `${r.grade}-${r.section}`,
          },
          { key: "status", header: "Status", cell: (r) => r.status },
        ]}
      />
    </div>
  );
}
