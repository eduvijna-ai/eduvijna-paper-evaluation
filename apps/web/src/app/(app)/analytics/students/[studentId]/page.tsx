"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { B12Sections } from "@/components/analytics/B12Sections";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  ConceptMasteryBar,
  ErrorDistribution,
} from "@/components/learning/LearningComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import {
  formatAnalyticsPercentage,
  isLiveStudentAnalytics,
  type LiveStudentAnalytics,
  type StudentAnalytics,
} from "@/lib/types/domain";
import type { ErrorCode } from "@/lib/types/enums";

function MockStudentAnalyticsView({
  data,
  studentId,
}: {
  data: StudentAnalytics;
  studentId: string;
}) {
  return (
    <>
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

      <B12Sections studentId={studentId} />
    </>
  );
}

function LiveStudentAnalyticsView({
  data,
  studentId,
}: {
  data: LiveStudentAnalytics;
  studentId: string;
}) {
  const learningLive = getApiCapabilities().learning === "live";
  const errorItems = data.error_distribution.map((e) => ({
    code: e.code as ErrorCode,
    count: e.count,
  }));

  return (
    <>
      <PageHeader
        title="Student analytics"
        description={data.student.display_name}
        breadcrumbs={[
          { label: "Analytics" },
          { label: "Students" },
          {
            label:
              data.student.external_ref ??
              data.student.student_code ??
              data.student.id.slice(0, 8),
          },
        ]}
        actions={
          learningLive ? (
            <Link
              href={`/learning/${studentId}`}
              data-testid="open-learning-plan"
              className="rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
            >
              Open learning plan
            </Link>
          ) : undefined
        }
      />

      {!learningLive && (
        <p
          data-testid="learning-not-live-boundary"
          className="mb-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600"
        >
          Learning recommendations are not live yet. Analytics below reflect
          published ledger evidence only.
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          {
            label: "Published assessments",
            value: String(data.published_assessment_count),
          },
          {
            label: "Published attempts",
            value: String(data.published_attempt_count),
          },
          {
            label: "Average percentage",
            value: formatAnalyticsPercentage(data.average_percentage),
          },
          {
            label: "Materialization",
            value: String(data.materialization_status),
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
        <section
          data-testid="concept-signals-section"
          className="rounded-md border border-slate-200 bg-white p-4 lg:col-span-2"
        >
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Current evidence signals
          </h2>
          <p className="mb-3 text-xs text-slate-500">
            Concept / execution / procedure signals from current mastery
            evidence (B8) — not longitudinal mastery state.
          </p>
          <ul className="space-y-4">
            {data.concept_signals.map((signal) => (
              <li
                key={signal.curriculum_node_id}
                className="rounded-md border border-slate-100 p-3"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                  <span className="font-medium">
                    {signal.code} · {signal.title}
                  </span>
                  <span className="tabular-nums text-slate-600">
                    mean evidence score{" "}
                    {signal.mean_score_ratio === null
                      ? "—"
                      : `${Math.round(signal.mean_score_ratio * 100)}%`}
                  </span>
                </div>
                <dl className="mt-2 grid gap-2 text-xs text-slate-600 sm:grid-cols-3">
                  <div>
                    <dt className="font-semibold text-slate-700">Concept</dt>
                    <dd>
                      {signal.concept.signal} ({signal.concept.strong_count}S /{" "}
                      {signal.concept.weak_count}W /{" "}
                      {signal.concept.inconclusive_count}I)
                    </dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-slate-700">Execution</dt>
                    <dd>
                      {signal.execution.signal} (
                      {signal.execution.strong_count}S /{" "}
                      {signal.execution.weak_count}W /{" "}
                      {signal.execution.inconclusive_count}I)
                    </dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-slate-700">Procedure</dt>
                    <dd>
                      {signal.procedure.signal} (
                      {signal.procedure.strong_count}S /{" "}
                      {signal.procedure.weak_count}W /{" "}
                      {signal.procedure.inconclusive_count}I)
                    </dd>
                  </div>
                </dl>
              </li>
            ))}
            {data.concept_signals.length === 0 && (
              <li className="text-sm text-slate-500">
                No mastery evidence signals yet.
              </li>
            )}
          </ul>
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4 lg:col-span-2">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Error distribution
          </h2>
          <p className="mb-3 text-xs text-slate-500">
            Reviewed error evidence from published mastery rows (not recurring
            mock errors).
          </p>
          {errorItems.length > 0 ? (
            <ErrorDistribution items={errorItems} />
          ) : (
            <p className="text-sm text-slate-500">No error evidence recorded.</p>
          )}
        </section>
      </div>

      <B12Sections studentId={studentId} />
    </>
  );
}

export default function StudentAnalyticsPage({
  params,
}: {
  params: Promise<{ studentId: string }>;
}) {
  const { studentId } = use(params);
  const live = getApiCapabilities().analytics === "live";
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["student-analytics-page", studentId],
    queryFn: () => api.getStudentAnalytics(studentId),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="student-analytics-page">
      {live && isLiveStudentAnalytics(data) ? (
        <LiveStudentAnalyticsView data={data} studentId={studentId} />
      ) : (
        <MockStudentAnalyticsView
          data={data as StudentAnalytics}
          studentId={studentId}
        />
      )}
    </div>
  );
}
