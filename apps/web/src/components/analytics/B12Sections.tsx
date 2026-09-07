"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getApiCapabilities } from "@/lib/api/capabilities";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import {
  formatMasteryRatio,
  type MistakeNotebookEntry,
  type StudentMasteryState,
  type StudentMasteryTrend,
  type StudentMistakeNotebook,
  type StudentRecoverableMarks,
  type StudentRepeatedErrors,
} from "@/lib/types/domain";

function SectionShell({
  testId,
  title,
  subtitle,
  children,
}: {
  testId: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section
      data-testid={testId}
      className="rounded-md border border-slate-200 bg-white p-4 lg:col-span-2"
    >
      <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
      {subtitle ? (
        <p className="mt-1 text-xs text-slate-500">{subtitle}</p>
      ) : null}
      <div className="mt-3">{children}</div>
    </section>
  );
}

function QueryBoundary({
  isLoading,
  isError,
  onRetry,
  children,
}: {
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
  children: React.ReactNode;
}) {
  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState onRetry={onRetry} />;
  return <>{children}</>;
}

function LongitudinalMasteryBody({
  state,
  trend,
}: {
  state: StudentMasteryState;
  trend: StudentMasteryTrend;
}) {
  return (
    <>
      <p className="mb-3 text-xs text-slate-500">
        Longitudinal mastery state (distinct from current evidence signals).{" "}
        <span className="font-mono text-slate-600">
          {state.algorithm_version} · {state.source}
        </span>
      </p>
      {state.items.length === 0 ? (
        <p className="text-sm text-slate-500">
          No longitudinal mastery state yet.
        </p>
      ) : (
        <ul className="space-y-3">
          {state.items.map((item) => (
            <li
              key={item.curriculum_node_id}
              className="rounded-md border border-slate-100 p-3"
            >
              <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">
                  {item.code} · {item.title}
                </span>
                <span className="tabular-nums text-slate-600">
                  {item.evidence_count} evidence row
                  {item.evidence_count === 1 ? "" : "s"}
                </span>
              </div>
              <dl className="mt-2 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                <div>
                  <dt className="font-semibold text-slate-700">Concept</dt>
                  <dd>
                    {item.insufficient_concept_evidence
                      ? "Insufficient evidence"
                      : formatMasteryRatio(item.concept_mastery)}{" "}
                    ({item.concept_decisive_count} decisive /{" "}
                    {item.concept_inconclusive_count} inconclusive)
                  </dd>
                </div>
                <div>
                  <dt className="font-semibold text-slate-700">Execution</dt>
                  <dd>
                    {item.insufficient_execution_evidence
                      ? "Insufficient evidence"
                      : formatMasteryRatio(item.execution_accuracy)}{" "}
                    ({item.execution_decisive_count} decisive /{" "}
                    {item.execution_inconclusive_count} inconclusive)
                  </dd>
                </div>
              </dl>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-4 border-t border-slate-100 pt-3">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
          Trend points
        </h3>
        {trend.points.length === 0 ? (
          <p className="text-sm text-slate-500">No mastery trend snapshots yet.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {trend.points.map((point) => (
              <li
                key={`${point.published_result_id}-${point.curriculum_node_id}`}
                className="flex flex-wrap justify-between gap-2"
              >
                <span>
                  {point.assessment_code} · {point.code}{" "}
                  <span className="text-xs text-slate-500">
                    {new Date(point.effective_at).toLocaleDateString()}
                  </span>
                </span>
                <span className="tabular-nums text-slate-600">
                  C {formatMasteryRatio(point.concept_mastery)} · E{" "}
                  {formatMasteryRatio(point.execution_accuracy)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}

function RepeatedErrorsBody({ data }: { data: StudentRepeatedErrors }) {
  if (data.items.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No recurring academic errors across published results.
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {data.items.map((item) => (
        <li
          key={item.error_code}
          className="rounded-md border border-slate-100 p-3 text-sm"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-medium text-slate-800">{item.error_code}</span>
            <span className="tabular-nums text-slate-600">
              {item.occurrence_count}× · {item.distinct_published_result_count}{" "}
              results · {item.distinct_assessment_count} assessments
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            First {new Date(item.first_seen_at).toLocaleDateString()} · Last{" "}
            {new Date(item.last_seen_at).toLocaleDateString()}
          </p>
        </li>
      ))}
    </ul>
  );
}

function RecoverableMarksBody({ data }: { data: StudentRecoverableMarks }) {
  return (
    <>
      <p
        data-testid="b12-recoverable-disclaimer"
        className="mb-3 rounded-md border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600"
      >
        {data.disclaimer}
      </p>
      <div className="mb-3 grid gap-3 sm:grid-cols-3">
        {[
          { label: "Total lost", value: data.total_lost_marks },
          {
            label: "Attributed recoverable",
            value: data.attributed_potentially_recoverable_marks,
          },
          { label: "Unattributed", value: data.unattributed_lost_marks },
        ].map((card) => (
          <div
            key={card.label}
            className="rounded-md border border-slate-100 px-3 py-2"
          >
            <div className="text-xs uppercase tracking-wide text-slate-500">
              {card.label}
            </div>
            <div className="mt-1 text-lg font-semibold tabular-nums">
              {card.value}
            </div>
          </div>
        ))}
      </div>
      {data.items.length === 0 ? (
        <p className="text-sm text-slate-500">
          No attributed potentially recoverable marks.
        </p>
      ) : (
        <ul className="space-y-2 text-sm">
          {data.items.map((item) => (
            <li
              key={item.error_code}
              className="flex flex-wrap justify-between gap-2 rounded-md border border-slate-100 p-3"
            >
              <span className="font-medium">{item.error_code}</span>
              <span className="tabular-nums text-slate-600">
                {item.potentially_recoverable_marks} marks · {item.occurrence_count}
                ×
                {item.percent_of_total_lost !== null
                  ? ` · ${item.percent_of_total_lost.toFixed(1)}% of lost`
                  : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

function MistakeNotebookBody({
  data,
  studentId,
}: {
  data: StudentMistakeNotebook;
  studentId: string;
}) {
  const learningLive = getApiCapabilities().learning === "live";
  const sorted = [...data.entries].sort(
    (a, b) =>
      new Date(a.effective_at).getTime() - new Date(b.effective_at).getTime(),
  );

  if (sorted.length === 0) {
    return (
      <p className="text-sm text-slate-500">No mistake notebook entries yet.</p>
    );
  }

  return (
    <ul className="space-y-3">
      {sorted.map((entry: MistakeNotebookEntry) => (
        <li
          key={entry.id}
          className="rounded-md border border-slate-100 p-3 text-sm"
        >
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <span className="font-medium">
              {entry.assessment_code} · {entry.question_code} ·{" "}
              {entry.academic_error_code}
            </span>
            <span className="tabular-nums text-slate-600">
              {entry.final_score}/{entry.max_mark}
            </span>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {new Date(entry.effective_at).toLocaleDateString()} ·{" "}
            {entry.recommended_practice_kind}
            {entry.curriculum_nodes.length > 0
              ? ` · ${entry.curriculum_nodes.map((n) => n.code).join(", ")}`
              : ""}
          </p>
          {entry.deduction_reasons.length > 0 ? (
            <p className="mt-1 text-xs text-slate-600">
              {entry.deduction_reasons.join("; ")}
            </p>
          ) : null}
          {learningLive &&
          entry.linked_learning_recommendation_ids.length > 0 ? (
            <Link
              href={`/learning/${studentId}`}
              className="mt-2 inline-block text-xs font-medium text-teal-800 hover:underline"
            >
              Open linked learning recommendations
            </Link>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

/**
 * B12 longitudinal mastery / mistake intelligence sections for student analytics.
 * No resource assignment UI — curriculum-linked practice context only.
 */
export function B12Sections({ studentId }: { studentId: string }) {
  const masteryStateQuery = useQuery({
    queryKey: ["b12-mastery-state", studentId],
    queryFn: () => api.getStudentMasteryState(studentId),
  });
  const masteryTrendQuery = useQuery({
    queryKey: ["b12-mastery-trend", studentId],
    queryFn: () => api.getStudentMasteryTrend(studentId),
  });
  const repeatedQuery = useQuery({
    queryKey: ["b12-repeated-errors", studentId],
    queryFn: () => api.getStudentRepeatedErrors(studentId),
  });
  const recoverableQuery = useQuery({
    queryKey: ["b12-recoverable-marks", studentId],
    queryFn: () => api.getStudentRecoverableMarks(studentId),
  });
  const notebookQuery = useQuery({
    queryKey: ["b12-mistake-notebook", studentId],
    queryFn: () => api.getStudentMistakeNotebook(studentId),
  });

  const masteryLoading =
    masteryStateQuery.isLoading || masteryTrendQuery.isLoading;
  const masteryError = masteryStateQuery.isError || masteryTrendQuery.isError;

  return (
    <div className="mt-6 grid gap-6 lg:grid-cols-2">
      <SectionShell
        testId="b12-longitudinal-mastery"
        title="Longitudinal mastery"
        subtitle="Persisted concept vs execution mastery across published evidence (B12)."
      >
        <QueryBoundary
          isLoading={masteryLoading}
          isError={masteryError}
          onRetry={() => {
            void masteryStateQuery.refetch();
            void masteryTrendQuery.refetch();
          }}
        >
          {masteryStateQuery.data && masteryTrendQuery.data ? (
            <LongitudinalMasteryBody
              state={masteryStateQuery.data}
              trend={masteryTrendQuery.data}
            />
          ) : null}
        </QueryBoundary>
      </SectionShell>

      <SectionShell
        testId="b12-repeated-errors"
        title="Repeated academic errors"
        subtitle="Academic codes recurring across distinct published results (review conditions excluded)."
      >
        <QueryBoundary
          isLoading={repeatedQuery.isLoading}
          isError={repeatedQuery.isError}
          onRetry={() => void repeatedQuery.refetch()}
        >
          {repeatedQuery.data ? (
            <RepeatedErrorsBody data={repeatedQuery.data} />
          ) : null}
        </QueryBoundary>
      </SectionShell>

      <SectionShell
        testId="b12-recoverable-marks"
        title="Potentially recoverable marks"
        subtitle="Analytical estimate from final criterion deductions."
      >
        <QueryBoundary
          isLoading={recoverableQuery.isLoading}
          isError={recoverableQuery.isError}
          onRetry={() => void recoverableQuery.refetch()}
        >
          {recoverableQuery.data ? (
            <RecoverableMarksBody data={recoverableQuery.data} />
          ) : null}
        </QueryBoundary>
      </SectionShell>

      <SectionShell
        testId="b12-mistake-notebook"
        title="Mistake notebook"
        subtitle="Chronological academic mistakes from the published ledger."
      >
        <QueryBoundary
          isLoading={notebookQuery.isLoading}
          isError={notebookQuery.isError}
          onRetry={() => void notebookQuery.refetch()}
        >
          {notebookQuery.data ? (
            <MistakeNotebookBody
              data={notebookQuery.data}
              studentId={studentId}
            />
          ) : null}
        </QueryBoundary>
      </SectionShell>
    </div>
  );
}
