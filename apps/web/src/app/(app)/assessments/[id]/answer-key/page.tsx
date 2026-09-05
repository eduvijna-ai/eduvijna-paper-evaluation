"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function AssessmentAnswerKeyPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const answerKeyQuery = useQuery({
    queryKey: ["assessment-answer-key", id],
    queryFn: () => api.getAssessmentAnswerKey(id),
  });

  if (assessmentQuery.isLoading || answerKeyQuery.isLoading)
    return <LoadingState />;
  if (
    assessmentQuery.isError ||
    answerKeyQuery.isError ||
    !assessmentQuery.data ||
    !answerKeyQuery.data
  ) {
    return <ErrorState onRetry={() => void answerKeyQuery.refetch()} />;
  }

  return (
    <div data-testid="assessment-answer-key-page">
      <PageHeader
        title="Answer key"
        description={assessmentQuery.data.title}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: assessmentQuery.data.code, href: `/assessments/${id}` },
          { label: "Answer key" },
        ]}
      />
      <ul className="space-y-3">
        {answerKeyQuery.data.map((step) => (
          <li
            key={step.id}
            data-testid={`answer-key-step-${step.id}`}
            className="rounded-md border border-slate-200 bg-white p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {step.question_id} · Step {step.step_index + 1}
                </div>
                <p className="mt-1 text-sm text-slate-800">{step.content}</p>
              </div>
              <div className="text-sm font-semibold tabular-nums text-slate-900">
                {step.marks} marks
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
