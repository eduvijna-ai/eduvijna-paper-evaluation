"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function AssessmentRubricPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const rubricQuery = useQuery({
    queryKey: ["assessment-rubric", id],
    queryFn: () => api.getAssessmentRubric(id),
  });

  if (assessmentQuery.isLoading || rubricQuery.isLoading)
    return <LoadingState />;
  if (
    assessmentQuery.isError ||
    rubricQuery.isError ||
    !assessmentQuery.data ||
    !rubricQuery.data
  ) {
    return <ErrorState onRetry={() => void rubricQuery.refetch()} />;
  }

  return (
    <div data-testid="assessment-rubric-page">
      <PageHeader
        title="Rubric & answer key"
        description={assessmentQuery.data.title}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: assessmentQuery.data.code, href: `/assessments/${id}` },
          { label: "Rubric" },
        ]}
      />
      <ul className="space-y-3">
        {rubricQuery.data.map((criterion) => (
          <li
            key={criterion.id}
            className="rounded-md border border-slate-200 bg-white p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-900">
                  {criterion.label}
                </div>
                <p className="mt-1 text-sm text-slate-600">
                  {criterion.description}
                </p>
                <p className="mt-2 text-xs text-slate-400">
                  Question {criterion.question_id}
                </p>
              </div>
              <div className="text-sm font-semibold tabular-nums">
                {criterion.max_marks} marks
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
