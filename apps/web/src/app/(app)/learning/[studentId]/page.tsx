"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  ErrorDistribution,
  LearningPathStep,
  TopicPriorityCard,
} from "@/components/learning/LearningComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function AdaptiveLearningPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["adaptive-learning", studentId],
    queryFn: () => api.getAdaptiveLearning(studentId),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="adaptive-learning-page">
      <PageHeader
        title="Adaptive learning"
        description={`Priority topics and sequenced path for ${data.student.display_name}`}
        breadcrumbs={[
          { label: "Learning" },
          { label: data.student.external_ref },
        ]}
        actions={
          <Link
            href={`/learning/${studentId}/improvement-assessment`}
            data-testid="improvement-assessment-link"
            className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
          >
            Improvement assessment
          </Link>
        }
      />

      <section className="grid gap-3 lg:grid-cols-3">
        {data.priorities.map((topic) => (
          <TopicPriorityCard key={topic.id} topic={topic} />
        ))}
      </section>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Learning path
          </h2>
          <ol className="space-y-2">
            {data.path.map((step, index) => (
              <LearningPathStep key={step.id} step={step} index={index} />
            ))}
          </ol>
        </section>
        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Error distribution
          </h2>
          <ErrorDistribution items={data.error_distribution} />
        </section>
      </div>
    </div>
  );
}
