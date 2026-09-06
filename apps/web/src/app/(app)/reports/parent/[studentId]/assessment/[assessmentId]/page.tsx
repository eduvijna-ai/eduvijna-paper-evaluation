"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import {
  ParentFriendlyInsight,
  ReportSection,
} from "@/components/reports/ReportSection";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function ParentReportPage({
  params,
}: {
  params: Promise<{ studentId: string; assessmentId: string }>;
}) {
  const { studentId, assessmentId } = use(params);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["parent-report", studentId, assessmentId],
    queryFn: () => api.getParentReport(studentId, assessmentId),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  return (
    <div data-testid="parent-report-page">
      <PageHeader
        title="Parent report"
        description="Plain-language summary — no technical AI or pipeline language."
        breadcrumbs={[
          { label: "Reports" },
          { label: "Parent" },
          { label: data.student_display_name },
        ]}
      />
      <div className="mx-auto max-w-2xl rounded-md border border-slate-200 bg-white px-5">
        <ReportSection title="Overview">
          <p className="text-lg text-slate-900">{data.score_summary}</p>
          <p className="mt-2 text-sm text-slate-600">{data.assessment_title}</p>
        </ReportSection>
        <ReportSection title="What went well">
          <ParentFriendlyInsight title="Strengths" items={data.what_went_well} />
        </ReportSection>
        <ReportSection title="What to practice">
          <ParentFriendlyInsight
            title="Practice areas"
            items={data.what_to_practice}
          />
        </ReportSection>
        <ReportSection title="How you can help">
          <ParentFriendlyInsight title="At home" items={data.how_to_help} />
        </ReportSection>
        <ReportSection title="Next step">
          <p className="text-sm text-slate-800">{data.next_step}</p>
        </ReportSection>
      </div>
    </div>
  );
}
