"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  ConceptMasteryBar,
  ErrorDistribution,
} from "@/components/learning/LearningComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function StudentAnalyticsPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["student-analytics-page", studentId],
    queryFn: () => api.getStudentAnalytics(studentId),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="student-analytics-page">
      <PageHeader
        title="Student analytics"
        description={data.student.display_name}
        breadcrumbs={[
          { label: "Analytics" },
          { label: "Students" },
          { label: data.student.external_ref },
        ]}
        actions={
          <Link
            href={`/learning/${studentId}`}
            className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
          >
            Open learning plan
          </Link>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-md border border-slate-200 bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500">
            Assessments taken
          </div>
          <div className="mt-2 text-2xl font-semibold tabular-nums">
            {data.assessments_taken}
          </div>
        </div>
        <div className="rounded-md border border-slate-200 bg-white p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500">
            Average percentage
          </div>
          <div className="mt-2 text-2xl font-semibold tabular-nums">
            {data.average_percentage}%
          </div>
        </div>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">Trend</h2>
          <ul className="space-y-2 text-sm">
            {data.trend.map((t) => (
              <li key={t.assessment_code} className="flex justify-between">
                <span>{t.assessment_code}</span>
                <span className="tabular-nums">{t.percentage}%</span>
              </li>
            ))}
          </ul>
        </section>
        <section className="rounded-md border border-slate-200 bg-white p-4 space-y-3">
          <h2 className="text-sm font-semibold text-slate-800">
            Concept mastery
          </h2>
          {data.concept_mastery.map((c) => (
            <ConceptMasteryBar
              key={c.concept}
              concept={c.concept}
              mastery={c.mastery}
            />
          ))}
        </section>
        <section className="rounded-md border border-slate-200 bg-white p-4 lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Recurring errors
          </h2>
          <ErrorDistribution items={data.recurring_errors} />
        </section>
      </div>
    </div>
  );
}
