"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ReportSection } from "@/components/reports/ReportSection";
import {
  ErrorCategoryBadge,
  ScoreDisplay,
} from "@/components/evaluation/ScoreComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";
import { formatScorePair } from "@/lib/helpers/score";

export default function TeacherReportPage({
  params,
}: {
  params: Promise<{ studentId: string; assessmentId: string }>;
}) {
  const { studentId, assessmentId } = use(params);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["teacher-report", studentId, assessmentId],
    queryFn: () => api.getTeacherReport!(studentId, assessmentId),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="teacher-report-page">
      <PageHeader
        title="Teacher diagnostic report"
        description={`${data.student.display_name} · ${data.assessment.title}`}
        breadcrumbs={[
          { label: "Reports" },
          { label: "Teacher" },
          { label: data.student.display_name },
        ]}
      />
      <div className="rounded-md border border-slate-200 bg-white px-4">
        <ReportSection title="Score">
          <ScoreDisplay
            score={data.total_score}
            max={data.max_total_score}
            size="lg"
          />
          <p
            data-testid="teacher-snapshot-hash"
            className="mt-2 break-all font-mono text-xs text-slate-500"
          >
            Snapshot {data.ledger_snapshot_hash.slice(0, 16)}…
          </p>
        </ReportSection>

        <ReportSection title="Question diagnostics">
          <div className="space-y-4">
            {data.questions.map((q) => (
              <div
                key={q.question_id}
                data-testid={`teacher-question-${q.question_id}`}
                className="rounded-md border border-slate-100 p-3"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="text-sm font-semibold text-slate-900">
                    {q.question_code}
                  </h3>
                  <span className="text-sm tabular-nums text-slate-700">
                    {formatScorePair(q.final_score, q.max_mark)} ·{" "}
                    {q.workflow_state}
                  </span>
                </div>
                {q.error_codes.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {q.error_codes.map((code) => (
                      <ErrorCategoryBadge
                        key={code}
                        code={code as import("@/lib/types/enums").ErrorCode}
                      />
                    ))}
                  </div>
                )}
                {q.criterion_decisions.length > 0 && (
                  <ul className="mt-2 space-y-1 text-xs text-slate-600">
                    {q.criterion_decisions.map((c, idx) => (
                      <li key={idx}>
                        {String(c.criterion_label ?? c.criterion_code ?? "Criterion")}
                        {": "}
                        {c.final_marks != null ? String(c.final_marks) : "—"}/
                        {String(c.max_marks ?? "—")}
                        {c.deduction_reason
                          ? ` — ${String(c.deduction_reason)}`
                          : ""}
                      </li>
                    ))}
                  </ul>
                )}
                {q.confidences && (
                  <p className="mt-2 text-xs text-slate-500">
                    Confidences: eval{" "}
                    {q.confidences.evaluation != null
                      ? Math.round(q.confidences.evaluation * 100)
                      : "—"}
                    % · math{" "}
                    {q.confidences.math_verification != null
                      ? Math.round(q.confidences.math_verification * 100)
                      : "—"}
                    %
                  </p>
                )}
              </div>
            ))}
          </div>
        </ReportSection>
      </div>
    </div>
  );
}
