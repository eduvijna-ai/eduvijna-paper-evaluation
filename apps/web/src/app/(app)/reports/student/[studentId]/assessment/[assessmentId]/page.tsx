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
import { QuestionScore } from "@/components/evaluation/ScoreComponents";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function StudentReportPage({
  params,
}: {
  params: Promise<{ studentId: string; assessmentId: string }>;
}) {
  const { studentId, assessmentId } = use(params);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["student-report", studentId, assessmentId],
    queryFn: () => api.getStudentReport(studentId, assessmentId),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const live = Boolean(data.live_published);

  return (
    <div data-testid="student-report-page">
      <PageHeader
        title="Student report"
        description={`${data.student.display_name} · ${data.assessment.title}`}
        breadcrumbs={[
          { label: "Reports" },
          { label: data.student.external_ref },
          { label: data.assessment.code },
        ]}
      />
      <div className="rounded-md border border-slate-200 bg-white px-4">
        <ReportSection title="Score">
          <ScoreDisplay
            score={data.total_score}
            max={data.max_marks}
            size="lg"
          />
          <p className="mt-1 text-sm text-slate-600">
            {data.percentage}% overall
          </p>
        </ReportSection>

        <ReportSection title="Question-wise">
          <div className="space-y-2">
            {data.question_summaries.map((q) => (
              <div key={q.question_id} className="space-y-1">
                <QuestionScore
                  code={q.question_code}
                  score={
                    live
                      ? (q.final_score ?? 0)
                      : (q.final_score ?? q.proposed_score)
                  }
                  max={q.max_mark}
                  state={q.workflow_state}
                />
                {q.error_codes.length > 0 && (
                  <div className="flex flex-wrap gap-1 pl-1">
                    {q.error_codes.map((code) => (
                      <ErrorCategoryBadge key={code} code={code} />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </ReportSection>

        {data.evidence_highlights.length > 0 && (
          <ReportSection title="Evidence">
            <ul className="space-y-2 text-sm">
              {data.evidence_highlights.map((e) => (
                <li key={`${e.question_code}-${e.excerpt}`}>
                  <span className="font-medium">{e.question_code}</span> ·{" "}
                  <span className="text-slate-500">{e.outcome}</span>
                  <div className="text-slate-700">{e.excerpt}</div>
                </li>
              ))}
            </ul>
          </ReportSection>
        )}

        {data.corrected_approaches.length > 0 && (
          <ReportSection title="Corrected approach">
            <ul className="space-y-2 text-sm">
              {data.corrected_approaches.map((c) => (
                <li key={c.question_code}>
                  <span className="font-medium">{c.question_code}:</span>{" "}
                  {c.approach}
                </li>
              ))}
            </ul>
          </ReportSection>
        )}

        {!live && data.topic_focus.length > 0 && (
          <ReportSection title="Topics">
            <ul className="space-y-2 text-sm">
              {data.topic_focus.map((t) => (
                <li key={t.topic} className="flex justify-between gap-3">
                  <span>
                    Priority {t.priority}: {t.topic}
                  </span>
                  <span className="tabular-nums text-slate-500">
                    {Math.round(t.mastery * 100)}%
                  </span>
                </li>
              ))}
            </ul>
          </ReportSection>
        )}

        <ReportSection title="Strengths">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {data.strengths.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </ReportSection>

        <ReportSection title="Weaknesses">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {data.weaknesses.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </ReportSection>

        {!live && data.patterns.length > 0 && (
          <ReportSection title="Patterns">
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
              {data.patterns.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
          </ReportSection>
        )}

        <ReportSection title="Next action">
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">
            {data.next_actions.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </ReportSection>
      </div>
    </div>
  );
}
