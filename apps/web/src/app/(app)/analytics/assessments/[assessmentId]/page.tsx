"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { ErrorDistribution } from "@/components/learning/LearningComponents";
import { ErrorCategoryBadge } from "@/components/evaluation/ScoreComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function AssessmentAnalyticsPage({
  params,
}: {
  params: Promise<{ assessmentId: string }>;
}) {
  const { assessmentId } = use(params);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["assessment-analytics", assessmentId],
    queryFn: () => api.getAssessmentAnalytics(assessmentId),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="assessment-analytics-page">
      <PageHeader
        title="Assessment analytics"
        description={data.assessment.title}
        breadcrumbs={[
          { label: "Analytics" },
          { label: "Assessments" },
          { label: data.assessment.code },
        ]}
        actions={
          <StatusBadge
            kind="assessment"
            state={data.assessment.workflow_state}
          />
        }
      />

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { label: "Mean score", value: data.mean_score.toFixed(1) },
          { label: "Median score", value: String(data.median_score) },
          {
            label: "Pass rate",
            value: `${Math.round(data.pass_rate * 100)}%`,
          },
        ].map((card) => (
          <div
            key={card.label}
            className="rounded-md border border-slate-200 bg-white p-4"
          >
            <div className="text-xs uppercase tracking-wide text-slate-500">
              {card.label}
            </div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">
              {card.value}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Question difficulty
          </h2>
          <ul className="space-y-3">
            {data.question_difficulty.map((q) => (
              <li key={q.question_code}>
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{q.question_code}</span>
                  <span className="tabular-nums text-slate-600">
                    {q.mean_score_pct}% mean
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {q.common_errors.map((code) => (
                    <ErrorCategoryBadge key={code} code={code} />
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Error distribution
          </h2>
          <ErrorDistribution items={data.error_distribution} />
          <h3 className="mb-2 mt-6 text-sm font-semibold text-slate-800">
            Score bands
          </h3>
          <ul className="space-y-1 text-sm">
            {data.score_bands.map((b) => (
              <li key={b.label} className="flex justify-between">
                <span>{b.label}</span>
                <span className="tabular-nums">{b.count}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
