"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function AssessmentCurriculumMapPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const assessmentQuery = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });
  const mapQuery = useQuery({
    queryKey: ["assessment-curriculum-map", id],
    queryFn: () => api.getAssessmentCurriculumMap(id),
  });

  if (assessmentQuery.isLoading || mapQuery.isLoading) return <LoadingState />;
  if (
    assessmentQuery.isError ||
    mapQuery.isError ||
    !assessmentQuery.data ||
    !mapQuery.data
  ) {
    return <ErrorState onRetry={() => void mapQuery.refetch()} />;
  }

  return (
    <div data-testid="assessment-curriculum-map-page">
      <PageHeader
        title="Curriculum map"
        description={`Question → curriculum node links for ${assessmentQuery.data.title}`}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: assessmentQuery.data.code, href: `/assessments/${id}` },
          { label: "Curriculum map" },
        ]}
      />
      <div className="overflow-x-auto rounded-md border border-slate-200 bg-white">
        <table className="min-w-full text-left text-sm" data-testid="curriculum-map-table">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-3 py-2.5 font-medium">Question</th>
              <th className="px-3 py-2.5 font-medium">Curriculum nodes</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {mapQuery.data.map((row) => (
              <tr key={row.question_id} data-testid={`curriculum-map-row-${row.question_code}`}>
                <td className="px-3 py-2.5 font-medium text-slate-900">
                  {row.question_code}
                </td>
                <td className="px-3 py-2.5 text-slate-700">
                  {row.node_titles.length > 0
                    ? row.node_titles.join(" · ")
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
