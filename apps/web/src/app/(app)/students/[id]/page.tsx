"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import { ConceptMasteryBar } from "@/components/learning/LearningComponents";

export default function StudentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const studentQuery = useQuery({
    queryKey: ["student", id],
    queryFn: () => api.getStudent(id),
  });
  const analyticsQuery = useQuery({
    queryKey: ["student-analytics", id],
    queryFn: () => api.getStudentAnalytics(id),
  });

  if (studentQuery.isLoading || analyticsQuery.isLoading)
    return <LoadingState />;
  if (studentQuery.isError || !studentQuery.data)
    return <ErrorState onRetry={() => void studentQuery.refetch()} />;

  const student = studentQuery.data;
  const analytics = analyticsQuery.data;

  return (
    <div data-testid="student-detail-page">
      <PageHeader
        title={student.display_name}
        description={`Roll ${student.external_ref} · Grade ${student.grade}-${student.section}`}
        breadcrumbs={[
          { label: "Students", href: "/students" },
          { label: student.external_ref },
        ]}
        actions={
          <div className="flex gap-2">
            <Link
              href={`/reports/student/${student.id}/assessment/assess-demo-001`}
              className="rounded-md border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
            >
              Student report
            </Link>
            <Link
              href={`/learning/${student.id}`}
              className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
            >
              Adaptive learning
            </Link>
          </div>
        }
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="text-sm font-semibold text-slate-800">Profile</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">Status</dt>
              <dd>{student.status}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Parent email</dt>
              <dd>{student.parent_email ?? "—"}</dd>
            </div>
          </dl>
        </div>
        <div className="rounded-md border border-slate-200 bg-white p-4 space-y-3">
          <h2 className="text-sm font-semibold text-slate-800">
            Concept mastery
          </h2>
          {analytics?.concept_mastery.map((c) => (
            <ConceptMasteryBar
              key={c.concept}
              concept={c.concept}
              mastery={c.mastery}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
