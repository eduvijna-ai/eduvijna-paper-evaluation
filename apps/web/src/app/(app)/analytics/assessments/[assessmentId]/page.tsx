"use client";

import { use, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { ErrorDistribution } from "@/components/learning/LearningComponents";
import { ErrorCategoryBadge } from "@/components/evaluation/ScoreComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import {
  formatAnalyticsPassRate,
  formatAnalyticsPercentage,
  isLiveAssessmentAnalytics,
  type AssessmentAnalytics,
  type LiveAssessmentAnalytics,
} from "@/lib/types/domain";
import type { ErrorCode } from "@/lib/types/enums";

function MockAssessmentAnalyticsView({ data }: { data: AssessmentAnalytics }) {
  return (
    <>
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
    </>
  );
}

function LiveAssessmentAnalyticsView({
  data,
  onPassThresholdChange,
  passThresholdInput,
}: {
  data: LiveAssessmentAnalytics;
  passThresholdInput: string;
  onPassThresholdChange: (value: string) => void;
}) {
  const academicItems = data.error_distribution.academic.map((e) => ({
    code: e.code as ErrorCode,
    count: e.count,
  }));
  const reviewItems = data.error_distribution.review_conditions.map((e) => ({
    code: e.code as ErrorCode,
    count: e.count,
  }));

  return (
    <>
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-md border border-slate-200 bg-white p-4">
        <label className="text-sm text-slate-700">
          Pass threshold (%)
          <input
            data-testid="pass-threshold-input"
            type="number"
            min={0}
            max={100}
            step={1}
            placeholder="Blank = Not configured"
            value={passThresholdInput}
            onChange={(e) => onPassThresholdChange(e.target.value)}
            className="mt-1 block w-40 rounded-md border border-slate-200 px-3 py-2 text-sm"
          />
        </label>
        <p className="text-xs text-slate-500">
          Leave blank for Not configured. Pass rate uses published percentage
          scores only.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          {
            label: "Published attempts",
            value: String(data.published_attempt_count),
            testId: "analytics-published-attempts",
          },
          {
            label: "Unique students",
            value: String(data.unique_student_count),
            testId: "analytics-unique-students",
          },
          {
            label: "Mean %",
            value: formatAnalyticsPercentage(data.mean_percentage),
            testId: "analytics-mean-percentage",
          },
          {
            label: "Median %",
            value: formatAnalyticsPercentage(data.median_percentage),
            testId: "analytics-median-percentage",
          },
          {
            label: "Pass rate",
            value: formatAnalyticsPassRate(
              data.pass_rate,
              data.pass_threshold_percent,
            ),
            testId: "analytics-pass-rate",
          },
          {
            label: "Mastery coverage",
            value:
              data.mastery_coverage_ratio === null
                ? "—"
                : `${Math.round(data.mastery_coverage_ratio * 100)}%`,
            testId: "analytics-mastery-coverage",
          },
        ].map((card) => (
          <div
            key={card.label}
            data-testid={card.testId}
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
          data-testid="question-performance-section"
          className="rounded-md border border-slate-200 bg-white p-4"
        >
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Question performance
          </h2>
          <ul className="space-y-3">
            {data.question_performance.map((q) => (
              <li key={q.question_id}>
                <div className="flex justify-between text-sm">
                  <span className="font-medium">{q.question_code}</span>
                  <span className="tabular-nums text-slate-600">
                    {formatAnalyticsPercentage(q.mean_score_percent)} mean
                  </span>
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {q.attempt_count} attempts · {q.blank_count} blank ·{" "}
                  {q.full_credit_count} full credit
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {q.common_errors.map((err) => (
                    <ErrorCategoryBadge
                      key={`${q.question_code}-${err.code}`}
                      code={err.code as ErrorCode}
                    />
                  ))}
                </div>
              </li>
            ))}
            {data.question_performance.length === 0 && (
              <li className="text-sm text-slate-500">No published question performance yet.</li>
            )}
          </ul>
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Score distribution
          </h2>
          <ul className="space-y-1 text-sm">
            {data.score_distribution.map((b) => (
              <li
                key={`${b.lower_bound}-${b.upper_bound}`}
                className="flex justify-between"
              >
                <span>
                  {b.lower_bound}–{b.upper_bound}%
                </span>
                <span className="tabular-nums">{b.count}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Academic errors
          </h2>
          {academicItems.length > 0 ? (
            <ErrorDistribution items={academicItems} />
          ) : (
            <p className="text-sm text-slate-500">No academic errors recorded.</p>
          )}
        </section>

        <section className="rounded-md border border-slate-200 bg-white p-4">
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Review condition errors
          </h2>
          {reviewItems.length > 0 ? (
            <ErrorDistribution items={reviewItems} />
          ) : (
            <p className="text-sm text-slate-500">
              No review-condition errors recorded.
            </p>
          )}
        </section>

        <section
          data-testid="curriculum-performance-section"
          className="rounded-md border border-slate-200 bg-white p-4 lg:col-span-2"
        >
          <h2 className="mb-3 text-sm font-semibold text-slate-800">
            Curriculum performance
          </h2>
          <ul className="space-y-3">
            {data.curriculum_performance.map((node) => (
              <li
                key={node.curriculum_node_id}
                className="flex flex-wrap items-baseline justify-between gap-2 text-sm"
              >
                <span className="font-medium">
                  {node.code} · {node.title}
                </span>
                <span className="tabular-nums text-slate-600">
                  mean evidence score{" "}
                  {node.mean_score_ratio === null
                    ? "—"
                    : `${Math.round(node.mean_score_ratio * 100)}%`}
                  {" · "}
                  {node.strong_signal_count} strong / {node.weak_signal_count}{" "}
                  weak
                </span>
              </li>
            ))}
            {data.curriculum_performance.length === 0 && (
              <li className="text-sm text-slate-500">
                No curriculum mastery evidence materialized yet.
              </li>
            )}
          </ul>
        </section>
      </div>
    </>
  );
}

export default function AssessmentAnalyticsPage({
  params,
}: {
  params: Promise<{ assessmentId: string }>;
}) {
  const { assessmentId } = use(params);
  const live = getApiCapabilities().analytics === "live";
  const [passThresholdInput, setPassThresholdInput] = useState("");

  const passThresholdPercent = (() => {
    if (passThresholdInput.trim() === "") return undefined;
    const n = Number(passThresholdInput);
    return Number.isFinite(n) ? n : undefined;
  })();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["assessment-analytics", assessmentId, passThresholdPercent ?? null],
    queryFn: () =>
      api.getAssessmentAnalytics(
        assessmentId,
        live && passThresholdPercent !== undefined
          ? { passThresholdPercent }
          : undefined,
      ),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const title = isLiveAssessmentAnalytics(data)
    ? data.assessment.title
    : data.assessment.title;
  const code = isLiveAssessmentAnalytics(data)
    ? data.assessment.code
    : data.assessment.code;
  const workflowState = isLiveAssessmentAnalytics(data)
    ? undefined
    : data.assessment.workflow_state;

  return (
    <div data-testid="assessment-analytics-page">
      <PageHeader
        title="Assessment analytics"
        description={title}
        breadcrumbs={[
          { label: "Analytics" },
          { label: "Assessments" },
          { label: code },
        ]}
        actions={
          workflowState ? (
            <StatusBadge kind="assessment" state={workflowState} />
          ) : (
            <span className="rounded-md border border-slate-200 px-2 py-1 text-xs text-slate-600">
              {isLiveAssessmentAnalytics(data)
                ? data.assessment.status
                : "—"}
            </span>
          )
        }
      />

      {live && isLiveAssessmentAnalytics(data) ? (
        <LiveAssessmentAnalyticsView
          data={data}
          passThresholdInput={passThresholdInput}
          onPassThresholdChange={setPassThresholdInput}
        />
      ) : (
        <MockAssessmentAnalyticsView data={data as AssessmentAnalytics} />
      )}
    </div>
  );
}
