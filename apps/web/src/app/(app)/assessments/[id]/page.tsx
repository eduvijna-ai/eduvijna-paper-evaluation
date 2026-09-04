"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function AssessmentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="assessment-detail-page">
      <PageHeader
        title={data.title}
        description={`${data.code} · ${data.subject} · Grade ${data.grade}`}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: data.code },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            <StatusBadge kind="assessment" state={data.workflow_state} />
            <Link
              href={`/assessments/${id}/questions`}
              className="rounded-md border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
            >
              Questions
            </Link>
            <Link
              href={`/assessments/${id}/rubric`}
              className="rounded-md border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
            >
              Rubric
            </Link>
            <Link
              href={`/analytics/assessments/${id}`}
              className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
            >
              Analytics
            </Link>
          </div>
        }
      />
      <dl className="grid gap-3 rounded-md border border-slate-200 bg-white p-4 sm:grid-cols-3 text-sm">
        <div>
          <dt className="text-slate-500">Max marks</dt>
          <dd className="mt-1 font-semibold tabular-nums">{data.max_marks}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Questions</dt>
          <dd className="mt-1 font-semibold tabular-nums">
            {data.question_count}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Submissions</dt>
          <dd className="mt-1 font-semibold tabular-nums">
            {data.submission_count}
          </dd>
        </div>
      </dl>
    </div>
  );
}
