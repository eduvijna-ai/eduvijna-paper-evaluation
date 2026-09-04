"use client";

import Link from "next/link";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { PageHeader, StatusBadge } from "@/components/layout/PageHeader";
import { ErrorState, LoadingState } from "@/components/ui/FeedbackStates";

export default function AssessmentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["assessment", id],
    queryFn: () => api.getAssessment(id),
  });

  if (isLoading) return <LoadingState />;
  if (isError || !data) return <ErrorState onRetry={() => void refetch()} />;

  const navLinks = [
    {
      href: `/assessments/${id}/questions`,
      label: "Questions",
      testId: "link-questions",
    },
    {
      href: `/assessments/${id}/answer-key`,
      label: "Answer key",
      testId: "link-answer-key",
    },
    {
      href: `/assessments/${id}/rubric`,
      label: "Rubric",
      testId: "link-rubric",
    },
    {
      href: `/assessments/${id}/curriculum-map`,
      label: "Curriculum map",
      testId: "link-curriculum-map",
    },
    {
      href: `/analytics/assessments/${id}`,
      label: "Analytics",
      testId: "link-analytics",
      primary: true,
    },
  ];

  return (
    <div data-testid="assessment-detail-page">
      <PageHeader
        title={data.title}
        description={`${data.code} · ${data.subject} · Grade ${data.grade}`}
        breadcrumbs={[
          { label: "Assessments", href: "/assessments" },
          { label: data.code },
        ]}
        actions={
          <div className="flex flex-wrap gap-2">
            <StatusBadge kind="assessment" state={data.workflow_state} />
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                data-testid={link.testId}
                className={
                  link.primary
                    ? "rounded-md bg-teal-800 px-3 py-2 text-sm font-medium text-white hover:bg-teal-900"
                    : "rounded-md border border-slate-200 px-3 py-2 text-sm hover:bg-slate-50"
                }
              >
                {link.label}
              </Link>
            ))}
          </div>
        }
      />
      <dl className="grid gap-3 rounded-md border border-slate-200 bg-white p-4 sm:grid-cols-3 text-sm">
        <div>
          <dt className="text-slate-500">Max marks</dt>
          <dd className="mt-1 font-semibold tabular-nums">{data.max_marks}</dd>
        </div>
        <div>
          <dt className="text-slate-500">Questions</dt>
          <dd className="mt-1 font-semibold tabular-nums">
            {data.question_count}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">Submissions</dt>
          <dd className="mt-1 font-semibold tabular-nums">
            {data.submission_count}
          </dd>
        </div>
      </dl>

      <nav
        data-testid="assessment-subnav"
        className="mt-4 flex flex-wrap gap-2 border-t border-slate-200 pt-4"
        aria-label="Assessment sections"
      >
        {navLinks
          .filter((l) => !l.primary)
          .map((link) => (
            <Link
              key={`subnav-${link.href}`}
              href={link.href}
              className="rounded-md bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-800 hover:bg-slate-200"
            >
              {link.label}
            </Link>
          ))}
      </nav>
    </div>
  );
}
