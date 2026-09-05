"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { QuestionTree } from "@/components/evaluation/QuestionTree";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function AssessmentQuestionsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const questionsQuery = useQuery({
    queryKey: ["assessment-questions", id],
    queryFn: () => api.getAssessmentQuestions(id),
  });

  if (assessmentQuery.isLoading || questionsQuery.isLoading)
    return <LoadingState />;
  if (
    assessmentQuery.isError ||
    questionsQuery.isError ||
    !assessmentQuery.data ||
    !questionsQuery.data
  ) {
    return <ErrorState onRetry={() => void questionsQuery.refetch()} />;
  }

  return (
    <div data-testid="assessment-questions-page">
      <PageHeader
        title="Questions"
        description={assessmentQuery.data.title}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: assessmentQuery.data.code, href: `/assessments/${id}` },
          { label: "Questions" },
        ]}
      />
      <div className="rounded-md border border-slate-200 bg-white p-4">
        <QuestionTree questions={questionsQuery.data} />
      </div>
    </div>
  );
}
